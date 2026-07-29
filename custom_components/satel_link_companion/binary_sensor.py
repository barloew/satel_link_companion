"""Satel Link Companion — per-link status sensors.

Each link gets two status sensors on its device, both driven by the forwarding
engine's logical state (not the base output switch):

  * Forwarding ready (the gate) — the intuitive main status: whether the link is
    currently armed to forward. ALWAYS -> always on; ARMED_ONLY -> on while the
    partition is armed; ENTRY_DELAY -> on once the exit window has elapsed.
  * Forwarding active (diagnostic) — whether a violation is being forwarded to
    the panel right now. Keeps the original sensor's unique_id and "forwarding
    now" meaning, so existing automations keep working.

Both read the engine, so they reflect intent precisely and never flip to
"unavailable" when the base output momentarily drops off the bus. Availability
depends only on whether the base output is resolved at all (stable), so it does
not flip either.

Satel Link Companion deliberately does NOT re-create the base switches or output
sensors: those already exist in the base integration and are referenced rather
than duplicated. These status sensors are a new concept the base does not offer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, LINK_SUBENTRY_TYPES
from .runtime import Link

if TYPE_CHECKING:
    from . import SatelLinkConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: "SatelLinkConfigEntry",
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the ready + active status sensors per link subentry."""
    runtime = entry.runtime_data
    outputs = runtime.base.by_number("output") if runtime.base else {}
    zones_by_num = {z.number: z for z in runtime.model.zones} if runtime.model else {}

    for subentry in entry.subentries.values():
        if subentry.subentry_type not in LINK_SUBENTRY_TYPES:
            continue
        link = Link.from_dict(dict(subentry.data))
        wired = link.output_number in outputs
        # Item 2: device defaults to its base zone's name; item 3: nests under
        # its partition's grouping node.
        zone = zones_by_num.get(link.zone_number)
        device_name = zone.ha_name if zone and zone.ha_name else subentry.title
        partition = zone.partition if zone else None
        common: dict[str, Any] = dict(
            entry=entry,
            subentry_id=subentry.subentry_id,
            device_name=device_name,
            partition=partition,
            link=link,
            wired=wired,
        )
        async_add_entities(
            [SatelLinkGateSensor(**common), SatelLinkActiveSensor(**common)],
            config_subentry_id=subentry.subentry_id,
        )


class _LinkStatusSensor(BinarySensorEntity):
    """Base for the per-link status sensors, driven by the forwarding engine."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        *,
        entry: "SatelLinkConfigEntry",
        subentry_id: str,
        device_name: str,
        link: Link,
        partition: int | None,
        wired: bool,
    ) -> None:
        self._entry = entry
        self._subentry_id = subentry_id
        self._link = link
        self._wired = wired
        self._gate_ready = False
        self._active = False
        device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=device_name,
            manufacturer="Satel Link Companion",
            model="Link",
        )
        if partition is not None:
            device_info["via_device"] = (DOMAIN, f"partition_{partition}")
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        # Stable: only reflects whether the base output is resolved, never the
        # output's momentary availability — so this never flips.
        return self._wired

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full link chain so the user can see what is wired to what."""
        link = self._link
        return {
            "ha_source_sensor": link.source_entity_id,
            "satel_output": link.output_number,
            "satel_zone": link.zone_number,
            "forwarding": link.forwarding.value,
            "invert": link.invert,
            "entry_delay_s": link.entry_delay_s,
            "min_on_s": link.min_on_s,
        }

    async def async_added_to_hass(self) -> None:
        engine = getattr(self._entry.runtime_data, "engine", None)
        if engine is not None:
            self._gate_ready, self._active = engine.status_for(self._subentry_id)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._subentry_id}_status",
                self._on_status,
            )
        )

    @callback
    def _on_status(self, gate_ready: bool, active: bool) -> None:
        self._gate_ready = gate_ready
        self._active = active
        self.async_write_ha_state()


class SatelLinkGateSensor(_LinkStatusSensor):
    """Whether the link is currently armed to forward — the intuitive status."""

    _attr_translation_key = "link_ready"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._attr_unique_id = (
            f"{self._entry.entry_id}_link_ready_{self._link.output_number}"
        )

    @property
    def is_on(self) -> bool:
        return self._gate_ready


class SatelLinkActiveSensor(_LinkStatusSensor):
    """Whether a violation is being forwarded to the panel right now.

    Keeps the original link sensor's unique_id and "forwarding now" semantics so
    existing automations keep working — but sourced from the engine's logical
    state instead of the base output switch, so it no longer flips.
    """

    _attr_translation_key = "link_active"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._attr_unique_id = f"{self._entry.entry_id}_link_{self._link.output_number}"

    @property
    def is_on(self) -> bool:
        return self._active
