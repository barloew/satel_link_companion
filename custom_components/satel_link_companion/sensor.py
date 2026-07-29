"""Satel Link Companion — diagnostic sensors surfacing the bus events (module D).

The event engine fires three events on the bus (see EVENTS.md). They are useful
for automations but invisible in the UI, so each is mirrored by a diagnostic
sensor whose state is the time of the last such event and whose attributes carry
that event's payload:

  * Last violation  -> satel_link_companion_breach       (partition, window_s, zones)
  * Last arm blocked-> satel_link_companion_arm_blocked   (partition, zones)
  * Last arm failed -> satel_link_companion_arm_failed    (partition, reason, zones)

One set per config entry, grouped on the "Satel Link Companion" device.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_ARM_BLOCKED, EVENT_ARM_FAILED, EVENT_BREACH

if TYPE_CHECKING:
    from datetime import datetime

    from . import SatelLinkConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: "SatelLinkConfigEntry",
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the diagnostic event sensors."""
    async_add_entities(
        [
            SatelLinkBreachSensor(entry),
            SatelLinkArmBlockedSensor(entry),
            SatelLinkArmFailedSensor(entry),
        ]
    )


class _LastEventSensor(SensorEntity):
    """Timestamp of the last bus event of a kind, with its payload as attributes."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    _event: str
    _uid_suffix: str
    _attr_keys: tuple[str, ...]

    def __init__(self, entry: "SatelLinkConfigEntry") -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{self._uid_suffix}"
        runtime = getattr(entry, "runtime_data", None)
        hub_name = getattr(runtime, "base_hub_name", None) or "Satel Link Companion"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=hub_name,
            manufacturer="Satel Link Companion",
            model="Satel Link Companion",
        )
        self._when: datetime | None = None
        self._data: dict[str, Any] = {}

    @property
    def native_value(self) -> "datetime | None":
        return self._when

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {key: self._data.get(key) for key in self._attr_keys}
        if "zones" in self._attr_keys:
            attrs["zone_count"] = len(self._data.get("zones") or [])
        return attrs

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.hass.bus.async_listen(self._event, self._on_event))

    @callback
    def _on_event(self, event: Event) -> None:
        self._when = dt_util.utcnow()
        self._data = dict(event.data)
        self.async_write_ha_state()


class SatelLinkBreachSensor(_LastEventSensor):
    """Last partition breach (satel_link_companion_breach)."""

    _event = EVENT_BREACH
    _uid_suffix = "last_breach"
    _attr_translation_key = "last_breach"
    _attr_keys = ("partition", "window_s", "zones")


class SatelLinkArmBlockedSensor(_LastEventSensor):
    """Last arm blocked by violated zones (satel_link_companion_arm_blocked)."""

    _event = EVENT_ARM_BLOCKED
    _uid_suffix = "last_arm_blocked"
    _attr_translation_key = "last_arm_blocked"
    _attr_keys = ("partition", "zones")


class SatelLinkArmFailedSensor(_LastEventSensor):
    """Last failed master arm, after rollback (satel_link_companion_arm_failed)."""

    _event = EVENT_ARM_FAILED
    _uid_suffix = "last_arm_failed"
    _attr_translation_key = "last_arm_failed"
    _attr_keys = ("partition", "reason", "zones")
