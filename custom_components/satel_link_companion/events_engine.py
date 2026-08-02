"""Satel Link Companion — the event engine (module D): blockers and breach snapshots.

Runs alongside the link engine. It:

  * feeds the rolling zone history from the base integration's zone
    binary_sensors;
  * watches the partition alarm_control_panel entities and, when one turns
    `triggered`, fires `satel_link_companion_breach` with the zones breached in the
    lookback window;
  * answers the active pre-arm check (a service) with the zones blocking an
    arm, and fires `satel_link_companion_arm_blocked`.

All state comes from the base integration's entities — Satel Link Companion holds no
runtime socket. Events carry function names so automations can react
meaningfully ("a perimeter zone blocked arming", not "zone 12").
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable

from homeassistant.const import STATE_ON
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .blockers import find_blockers
from .const import EVENT_ARM_BLOCKED, EVENT_BREACH
from .history import ZoneHistory

if TYPE_CHECKING:
    from . import SatelLinkConfigEntry

_LOGGER = logging.getLogger(__name__)

STATE_TRIGGERED = "triggered"


class EventEngine:
    """Blocker checks and breach snapshots, driven by base-integration state."""

    def __init__(self, hass: HomeAssistant, entry: "SatelLinkConfigEntry") -> None:
        self._hass = hass
        self._entry = entry
        self._history = ZoneHistory()
        self._unsubscribe: list[Callable[[], None]] = []
        # entity_id -> zone number, and partition entity_id -> partition number
        self._zone_of: dict[str, int] = {}
        self._partition_of: dict[str, int] = {}
        self._partition_state: dict[str, str] = {}

    async def async_start(self) -> None:
        runtime = self._entry.runtime_data
        if runtime.base is None:
            _LOGGER.warning("Event engine idle: no base integration resolved")
            return

        # Size the history to the largest lookback anyone might ask for.
        settings = runtime.settings
        self._history.max_window = max(
            [settings.breach_lookback_s, *settings.partition_lookback.values(), 5.0]
        )

        zones = runtime.base.by_number("zone")
        partitions = runtime.base.by_number("partition")
        self._zone_of = {e.entity_id: n for n, e in zones.items()}
        self._partition_of = {e.entity_id: n for n, e in partitions.items()}

        # Seed the current partition states so we only react to *transitions*
        # into triggered.
        for entity_id in self._partition_of:
            if (state := self._hass.states.get(entity_id)) is not None:
                self._partition_state[entity_id] = state.state

        watched = list(self._zone_of) + list(self._partition_of)
        if watched:
            self._unsubscribe.append(
                async_track_state_change_event(
                    self._hass, watched, self._handle_change
                )
            )

    async def async_stop(self) -> None:
        for unsub in self._unsubscribe:
            unsub()
        self._unsubscribe.clear()

    @callback
    def _handle_change(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new = event.data["new_state"]
        if new is None:
            return
        if entity_id in self._zone_of:
            self._history.record(
                self._zone_of[entity_id], new.state == STATE_ON, time.monotonic()
            )
        elif entity_id in self._partition_of:
            self._partition_changed(entity_id, new.state)

    @callback
    def _partition_changed(self, entity_id: str, new_state: str) -> None:
        previous = self._partition_state.get(entity_id)
        self._partition_state[entity_id] = new_state
        if new_state == STATE_TRIGGERED and previous != STATE_TRIGGERED:
            self._fire_breach(self._partition_of[entity_id])

    def _live_name(self, entity_id: str | None, fallback: str) -> str:
        """The zone's current friendly name as shown in Home Assistant.

        Resolved live from the entity's state (which composes the device name
        for has_entity_name integrations, or a user rename), so a rename takes
        effect without re-running discovery. Falls back to the name captured at
        discovery when the entity or its friendly name is unavailable.
        """
        if entity_id:
            state = self._hass.states.get(entity_id)
            if state is not None:
                friendly = state.attributes.get("friendly_name")
                if friendly:
                    return friendly
        return fallback

    def _live_area(self, entity_id: str | None) -> str | None:
        """The zone's current area name — from the entity, or inherited from its
        device — resolved live. Returns None when the zone has no area.

        This is what disambiguates same-named zones (three "Raam" zones become
        "Raam (Ouderslaapkamer)", "Raam (Logeerkamer)", ...) in notifications.
        """
        if not entity_id:
            return None
        entity = er.async_get(self._hass).async_get(entity_id)
        if entity is None:
            return None
        area_id = entity.area_id
        if area_id is None and entity.device_id:
            device = dr.async_get(self._hass).async_get(entity.device_id)
            area_id = device.area_id if device else None
        if area_id is None:
            return None
        area = ar.async_get(self._hass).async_get_area(area_id)
        return area.name if area else None

    @callback
    def _fire_breach(self, partition: int) -> None:
        runtime = self._entry.runtime_data
        window = runtime.settings.window_for(partition)
        breached = self._history.snapshot(window, time.monotonic())

        zones = {z.number: z for z in runtime.model.zones} if runtime.model else {}
        payload_zones = [
            {
                "number": n,
                "name": (
                    self._live_name(zones[n].entity_id, zones[n].display_name)
                    if n in zones
                    else f"Zone {n}"
                ),
                "function": zones[n].function_name if n in zones else None,
                "area": self._live_area(zones[n].entity_id) if n in zones else None,
            }
            for n in sorted(breached)
            if zones.get(n) is None or zones[n].partition in (partition, None)
        ]
        self._hass.bus.async_fire(
            EVENT_BREACH,
            {"partition": partition, "window_s": window, "zones": payload_zones},
        )
        _LOGGER.info(
            "Breach in partition %d: %d zone(s) in the last %.1fs",
            partition,
            len(payload_zones),
            window,
        )

    def _partition_label(self, partition: int) -> str:
        """Partition as "Name (Number)" — the same convention as the UI node."""
        base = self._entry.runtime_data.base
        entity = (
            base.by_number("partition").get(partition) if base is not None else None
        )
        name = (
            self._live_name(entity.entity_id, f"Partitie {partition}")
            if entity is not None
            else f"Partitie {partition}"
        )
        return f"{name} ({partition})"

    def _blocker_payload(self, partition: int) -> list[dict]:
        """Zones blocking an arm of one partition, as event payload — WITHOUT
        firing. Callers decide: the per-partition service fires one event; the
        master aggregates several partitions into one consolidated event. Each
        zone carries its partition as a readable "Name (Number)" label.
        """
        runtime = self._entry.runtime_data
        if runtime.model is None or runtime.base is None:
            return []

        zone_entities = runtime.base.by_number("zone")

        def is_violated(number: int) -> bool:
            entity = zone_entities.get(number)
            if entity is None:
                return False
            state = self._hass.states.get(entity.entity_id)
            return state is not None and state.state == STATE_ON

        label = self._partition_label(partition)
        blockers = find_blockers(partition, runtime.model.zones, is_violated)
        return [
            {
                "number": b.number,
                "name": self._live_name(
                    zone_entities[b.number].entity_id
                    if b.number in zone_entities
                    else None,
                    b.name,
                ),
                "function": b.function_name,
                "area": self._live_area(
                    zone_entities[b.number].entity_id
                    if b.number in zone_entities
                    else None
                ),
                "partition": label,
            }
            for b in blockers
        ]

    async def async_check_arm(self, partition: int) -> list[dict]:
        """Active pre-arm check for ONE partition: return the blocking zones and
        fire `satel_link_companion_arm_blocked` if there are any."""
        payload = self._blocker_payload(partition)
        if payload:
            self._hass.bus.async_fire(
                EVENT_ARM_BLOCKED, {"partition": partition, "zones": payload}
            )
        return payload

    @callback
    def arm_blockers_for(
        self, partitions: list[int]
    ) -> tuple[int | None, list[dict]]:
        """Aggregate blocking zones across several partitions, WITHOUT firing.

        Returns (first_blocked_partition, zones) so the master can run one
        pre-flight over a whole mode and report every open zone at once,
        instead of one partition at a time.
        """
        first: int | None = None
        zones: list[dict] = []
        for partition in partitions:
            payload = self._blocker_payload(partition)
            if payload and first is None:
                first = partition
            zones.extend(payload)
        return first, zones

    @callback
    def fire_arm_blocked(self, zones: list[dict], partition: int | None) -> None:
        """Fire one consolidated `satel_link_companion_arm_blocked` event."""
        if not zones:
            return
        self._hass.bus.async_fire(
            EVENT_ARM_BLOCKED, {"partition": partition, "zones": zones}
        )
