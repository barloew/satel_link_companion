"""Mirror the base integration's device organisation.

By default the Satel Link Companion devices take their name and area from the
corresponding *base* integration objects, exactly as the user configured them
over there:

  * the hub device        -> the base integration's top-level (central) device
  * each link device       -> the base zone the link forwards to
  * partition grouping nodes (no entity) -> the base partition devices, with the
    link devices nested underneath via ``via_device``

Names are set as *defaults* through DeviceInfo, so a user rename via the UI
(name_by_user) always wins. Areas are only *filled in* when still empty, so
moving a device to a different area in the UI is never overwritten on reload.

Reading the base *device* (not just the entity) matters: a Satel partition's
name lives on its device, while its alarm_control_panel entity has no name of
its own.

The partition grouping nodes must exist *before* the link platforms are set up,
so the links' ``via_device`` resolves; areas are applied afterwards, once the
platforms have created their devices.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN, LINK_SUBENTRY_TYPES
from .runtime import Link

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from . import SatelLinkConfigEntry

_LOGGER = logging.getLogger(__name__)


def partition_node_identifier(number: int) -> tuple[str, str]:
    """Identifier of the grouping node for a base partition."""
    return (DOMAIN, f"partition_{number}")


@callback
def base_hub_name_area(
    hass: HomeAssistant, base_entry: "ConfigEntry"
) -> tuple[str | None, str | None]:
    """Name + area_id of the base integration's top-level (central) device."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        identifiers={(base_entry.domain, base_entry.entry_id)}
    )
    if device is None:
        # Fall back to the base entry's top-level device (no parent).
        for dev in dr.async_entries_for_config_entry(dev_reg, base_entry.entry_id):
            if dev.via_device_id is None:
                device = dev
                break
    if device is None:
        return None, None
    return (device.name_by_user or device.name, device.area_id)


@callback
def _base_device_of_entity(
    hass: HomeAssistant, entity_id: str | None
) -> tuple[str | None, str | None]:
    """Name + area_id of the device an entity lives on.

    For Satel partitions the friendly name sits on the *device*, not the
    alarm_control_panel entity, so we read the device.
    """
    if entity_id is None:
        return None, None
    ent = er.async_get(hass).async_get(entity_id)
    if ent is None or ent.device_id is None:
        return None, None
    dev = dr.async_get(hass).async_get(ent.device_id)
    if dev is None:
        return None, None
    return (dev.name_by_user or dev.name, dev.area_id)


@callback
def _link_partitions(entry: "SatelLinkConfigEntry") -> set[int]:
    """Partition numbers referenced by at least one link."""
    model = entry.runtime_data.model
    if model is None:
        return set()
    zones_by_num = {z.number: z for z in model.zones}
    used: set[int] = set()
    for subentry in entry.subentries.values():
        if subentry.subentry_type not in LINK_SUBENTRY_TYPES:
            continue
        try:
            link = Link.from_dict(dict(subentry.data))
        except (KeyError, TypeError, ValueError):
            continue
        zone = zones_by_num.get(link.zone_number)
        if zone is not None and zone.partition is not None:
            used.add(zone.partition)
    return used


@callback
def async_register_partition_nodes(
    hass: HomeAssistant, entry: "SatelLinkConfigEntry"
) -> None:
    """Create a grouping node (no entity) per used base partition (item 3).

    Only partitions that actually carry a link get a node, so every node has
    children and renders in the UI. Runs before the link platform so the links'
    ``via_device`` resolves. Name + area come from the base partition device.
    """
    existing = entry.runtime_data.base
    if existing is None:
        return
    dev_reg = dr.async_get(hass)
    base_partitions = existing.by_number("partition")
    for number in sorted(_link_partitions(entry)):
        base_ent = base_partitions.get(number)
        name, area_id = (
            _base_device_of_entity(hass, base_ent.entity_id)
            if base_ent is not None
            else (None, None)
        )
        if name:
            # Translatable device name: "{name} (n)". The device model
            # ("Partition") conveys the type, so the name itself is not prefixed.
            name_args = {
                "name": None,
                "translation_key": "partition_node",
                "translation_placeholders": {"name": name, "number": str(number)},
            }
        else:
            name_args = {"name": f"Partition {number}", "translation_key": None}
        node = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={partition_node_identifier(number)},
            manufacturer="Satel Link Companion",
            model="Partition",
            **name_args,
        )
        if node.area_id is None and area_id:
            dev_reg.async_update_device(node.id, area_id=area_id)


@callback
def async_apply_areas(hass: HomeAssistant, entry: "SatelLinkConfigEntry") -> None:
    """Fill in device areas from the base (items 1 + 2), only where still empty.

    Runs after the platforms created their devices. Names and ``via_device`` are
    set via DeviceInfo; only areas are applied here.
    """
    runtime = entry.runtime_data
    dev_reg = dr.async_get(hass)

    # Item 1: hub device area from the base central device.
    if runtime.base_hub_area_id:
        hub = dev_reg.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
        if hub is not None and hub.area_id is None:
            dev_reg.async_update_device(hub.id, area_id=runtime.base_hub_area_id)

    # Item 2: each link device area from its base zone. Read the zone's area from
    # the LIVE base registry (re-read every setup) rather than the stored
    # discovery model -- a model captured before a base/parsing change would
    # carry a stale (empty) area. Fall back to the model if the live read misses.
    base_zones = runtime.base.by_number("zone") if runtime.base else {}
    model_zones = (
        {z.number: z for z in runtime.model.zones} if runtime.model else {}
    )
    for subentry in entry.subentries.values():
        if subentry.subentry_type not in LINK_SUBENTRY_TYPES:
            continue
        try:
            link = Link.from_dict(dict(subentry.data))
        except (KeyError, TypeError, ValueError):
            continue
        base_zone = base_zones.get(link.zone_number)
        model_zone = model_zones.get(link.zone_number)
        area_id = (base_zone.area_id if base_zone else None) or (
            model_zone.area_id if model_zone else None
        )
        if not area_id:
            continue
        device = dev_reg.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
        if device is not None and device.area_id is None:
            dev_reg.async_update_device(device.id, area_id=area_id)
