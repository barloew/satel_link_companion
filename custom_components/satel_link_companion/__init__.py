"""Satel Link Companion — a companion for the Satel Integra Panel.

Satel Link Companion links Home Assistant sensors into the Satel Integra Panel as real,
armed Satel zones, and exposes Satel outputs (switches, roller-shutter covers)
in Home Assistant.

Runtime model: the ETHM accepts one client on the integration port, and the
base integration (satel_integra / ha_satel_integra_ext) owns it. Satel Link Companion
therefore holds no socket of its own at runtime — it drives the base
integration's output switches and reads arm state from its alarm_control_panel
entities. The only direct connection is the one-off discovery scan, which runs
with the base integration briefly unloaded.
"""

from __future__ import annotations

import logging
from types import MappingProxyType

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_PARTITION,
    DOMAIN,
    LINK_SUBENTRY_TYPES,
    SERVICE_CHECK_ARM,
    SUBENTRY_TYPE_CONTROL,
    SUBENTRY_TYPE_LINK,
    SUBENTRY_TYPE_MASTER,
)
from .events_engine import EventEngine
from .link_engine import LinkEngine
from .registry_ha import find_base_entry, read_existing
from .runtime import (
    OPT_CONTROLS,
    OPT_LINKS,
    OPT_MASTER,
    OPT_MODEL,
    Link,
    RuntimeData,
    load_controls_from_subentries,
    load_links_from_subentries,
    load_model,
    load_settings,
)

_LOGGER = logging.getLogger(__name__)

CONF_BASE_ENTRY = "base_entry_id"

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.SENSOR,
]

type SatelLinkConfigEntry = ConfigEntry[RuntimeData]


async def async_migrate_entry(
    hass: HomeAssistant, entry: SatelLinkConfigEntry
) -> bool:
    """Migrate old config entries to the config-subentry model.

    v1 -> v2 (0.2.0): links move from options to subentries.
    v2 -> v3 (0.2.5): controls move from options to subentries.
    """
    options = dict(entry.options)
    if entry.version < 2:
        _migrate_links_to_subentries(hass, entry)
        options.pop(OPT_LINKS, None)
    if entry.version < 3:
        _migrate_controls_to_subentries(hass, entry)
        options.pop(OPT_CONTROLS, None)
    if entry.version < 4:
        _migrate_master_to_subentries(hass, entry)
        options.pop(OPT_MASTER, None)
    if entry.version < 4:
        hass.config_entries.async_update_entry(entry, options=options, version=4)
    return True


@callback
def _migrate_master_to_subentries(
    hass: HomeAssistant, entry: SatelLinkConfigEntry
) -> None:
    """Create a master subentry from the old single OPT_MASTER entry.

    The old master had one partition list used for every mode, so it maps onto
    all three mode sets. MasterPanel.from_dict already applies a legacy
    "partitions" list to every mode, so passing it through is enough.
    """
    old = entry.options.get(OPT_MASTER)
    if not old:
        return
    if any(
        s.subentry_type == SUBENTRY_TYPE_MASTER for s in entry.subentries.values()
    ):
        return  # already migrated

    name = old.get("name", "Alarm master")
    partitions = [int(p) for p in old.get("partitions", [])]
    data = {
        "name": name,
        "home_partitions": partitions,
        "away_partitions": partitions,
        "night_partitions": partitions,
    }
    try:
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(data),
                subentry_type=SUBENTRY_TYPE_MASTER,
                title=name,
                unique_id="master_migrated",
            ),
        )
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to migrate the master panel")


@callback
def _migrate_controls_to_subentries(
    hass: HomeAssistant, entry: SatelLinkConfigEntry
) -> None:
    """Create a control subentry for each control previously in OPT_CONTROLS."""
    old = entry.options.get(OPT_CONTROLS)
    if not old:
        return
    if any(
        s.subentry_type == SUBENTRY_TYPE_CONTROL for s in entry.subentries.values()
    ):
        return  # already migrated

    for raw in old:
        num = raw.get("output_number")
        if num is None:
            continue
        platform = raw.get("platform", "switch")
        if platform != "cover":
            continue  # switches and read-only outputs are the base's job now
        data = {
            "output_number": int(num),
            "platform": "cover",
            "down_number": raw.get("down_number"),
        }
        try:
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(data),
                    subentry_type=SUBENTRY_TYPE_CONTROL,
                    title=f"Rolluik {num}",
                    unique_id=f"control_{num}",
                ),
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to migrate cover on output %s", num)


@callback
def _migrate_links_to_subentries(
    hass: HomeAssistant, entry: SatelLinkConfigEntry
) -> None:
    """Create a link subentry for each link previously stored in OPT_LINKS."""
    old = entry.options.get(OPT_LINKS)
    if not old:
        return
    if any(
        s.subentry_type in LINK_SUBENTRY_TYPES for s in entry.subentries.values()
    ):
        return  # already migrated

    for raw in old:
        try:
            link = Link.from_dict(raw)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Skipping a link that could not be migrated: %s", raw)
            continue
        state = hass.states.get(link.source_entity_id)
        src_name = state.name if state else link.source_entity_id
        title = f"{src_name} → uitgang {link.output_number} → zone {link.zone_number}"
        try:
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(link.to_dict()),
                    subentry_type=SUBENTRY_TYPE_LINK,
                    title=title,
                    unique_id=f"link_{link.output_number}",
                ),
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Failed to migrate link on output %s", link.output_number
            )


async def async_setup_entry(hass: HomeAssistant, entry: SatelLinkConfigEntry) -> bool:
    """Set up Satel Link Companion from a config entry."""
    options = dict(entry.options)

    runtime = RuntimeData(
        model=load_model(options[OPT_MODEL]) if options.get(OPT_MODEL) else None,
        links=load_links_from_subentries(entry),
        controls=load_controls_from_subentries(entry),
        settings=load_settings(options),
    )

    # Resolve the base integration's entities so we can drive its output
    # switches and read its arm state. Without it, links cannot forward.
    base_entry = None
    if base_id := {**entry.data, **options}.get(CONF_BASE_ENTRY):
        base_entry = hass.config_entries.async_get_entry(base_id)
    if base_entry is None:
        base_entry = find_base_entry(hass)
    if base_entry is not None:
        runtime.base = read_existing(hass, base_entry)
    else:
        _LOGGER.warning(
            "No Satel base integration found; links cannot forward until one is set up"
        )

    entry.runtime_data = runtime

    # Start the forwarding engine (links) and the event engine (blockers +
    # breach snapshots). Controls are entity platforms.
    runtime.engine = LinkEngine(hass, entry)
    await runtime.engine.async_start()
    runtime.events = EventEngine(hass, entry)
    await runtime.events.async_start()

    _async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_change))
    return True


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    """Register the domain-wide pre-arm check service, once."""
    if hass.services.has_service(DOMAIN, SERVICE_CHECK_ARM):
        return

    async def _check_arm(call: ServiceCall) -> ServiceResponse:
        partition = call.data[ATTR_PARTITION]
        for entry in hass.config_entries.async_entries(DOMAIN):
            runtime = getattr(entry, "runtime_data", None)
            if runtime and runtime.events:
                zones = await runtime.events.async_check_arm(partition)
                return {"blocked": bool(zones), "zones": zones}
        return {"blocked": False, "zones": []}

    hass.services.async_register(
        DOMAIN,
        SERVICE_CHECK_ARM,
        _check_arm,
        schema=vol.Schema({vol.Required(ATTR_PARTITION): cv.positive_int}),
        supports_response=SupportsResponse.ONLY,
    )


async def async_unload_entry(hass: HomeAssistant, entry: SatelLinkConfigEntry) -> bool:
    """Tear down Satel Link Companion."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and (runtime := entry.runtime_data):
        if runtime.engine:
            await runtime.engine.async_stop()
        if runtime.events:
            await runtime.events.async_stop()
    return unloaded


async def _async_reload_on_change(hass: HomeAssistant, entry: SatelLinkConfigEntry) -> None:
    """Reload when links/controls change in the options flow."""
    await hass.config_entries.async_reload(entry.entry_id)
