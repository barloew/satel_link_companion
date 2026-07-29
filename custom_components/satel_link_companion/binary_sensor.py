"""Satel Link Companion — link-status binary sensors.

One per configured link: whether the link is currently forwarding a violation
to the Satel Integra Panel. That is the driven output's state corrected for
polarity (invert), so it reads as the logical "violated" the panel sees.

Satel Link Companion deliberately does NOT re-create switches or read-only output sensors:
those already exist in the base integration (satel_integra / ha_satel_integra_ext)
and Satel Link Companion references them instead of duplicating. The one added entity here
is the link-status sensor, which is a new concept the base does not provide.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

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
    """Create a link-status sensor per link subentry (one per link device)."""
    runtime = entry.runtime_data
    outputs = runtime.base.by_number("output") if runtime.base else {}
    zones_by_num = {z.number: z for z in runtime.model.zones} if runtime.model else {}

    for subentry in entry.subentries.values():
        if subentry.subentry_type not in LINK_SUBENTRY_TYPES:
            continue
        link = Link.from_dict(dict(subentry.data))
        base = outputs.get(link.output_number)
        # Item 2: the link device defaults to its base zone's name; item 3: it
        # nests under its partition's grouping node.
        zone = zones_by_num.get(link.zone_number)
        device_name = zone.ha_name if zone and zone.ha_name else subentry.title
        partition = zone.partition if zone else None
        async_add_entities(
            [
                SatelLinkLinkSensor(
                    entry_id=entry.entry_id,
                    subentry_id=subentry.subentry_id,
                    device_name=device_name,
                    partition=partition,
                    link=link,
                    output_switch=base.entity_id if base else None,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SatelLinkLinkSensor(BinarySensorEntity):
    """Whether a link is currently forwarding a violation to the panel.

    Lives on its own per-link device; the attributes spell out the full chain:
    Home Assistant source sensor -> Satel switchable output -> Satel zone.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "link_forwarding"

    def __init__(
        self,
        *,
        entry_id: str,
        subentry_id: str,
        device_name: str,
        link: Link,
        output_switch: str | None,
        partition: int | None = None,
    ) -> None:
        self._watched = output_switch
        self._link = link
        self._invert = link.invert
        self._attr_unique_id = f"{entry_id}_link_{link.output_number}"
        device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=device_name,
            manufacturer="Satel Link Companion",
            model="Koppeling",
        )
        if partition is not None:
            device_info["via_device"] = (DOMAIN, f"partition_{partition}")
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        if self._watched is None:
            return False
        state = self.hass.states.get(self._watched)
        return state is not None and state.state != STATE_UNAVAILABLE

    @property
    def is_on(self) -> bool | None:
        """Forwarding a violation = base output active, corrected for polarity."""
        if self._watched is None:
            return None
        state = self.hass.states.get(self._watched)
        if state is None:
            return None
        return (state.state == STATE_ON) ^ self._invert

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
        if self._watched is None:
            return

        @callback
        def _changed(event) -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(self.hass, [self._watched], _changed)
        )
