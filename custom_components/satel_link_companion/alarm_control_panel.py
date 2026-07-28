"""Satel Link Companion — master alarm panel entities (module C).

One tile per master subentry that arms several partitions as a unit. HomeKit
couples one accessory to one alarm panel, so a master lets HomeKit (and the
normal HA UI) operate several partitions at once. Each mode (home / away /
night) drives its own partition set; only modes that have partitions are offered.

Shown state is the last commanded state, cross-checked against the underlying
partitions: if every partition is disarmed (e.g. from a keypad), the tile falls
back to disarmed so it never lies about being armed. The code is supplied per
command (or, for HomeKit, by the bridge's entity_config); it is passed through,
never stored.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN
from .master_engine import MasterEngine
from .runtime import MasterPanel, load_masters_from_subentries

if TYPE_CHECKING:
    from . import SatelLinkConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: "SatelLinkConfigEntry",
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one master panel per master subentry, each on its own device."""
    for subentry_id, title, master in load_masters_from_subentries(entry):
        async_add_entities(
            [SatelLinkMasterPanel(entry, subentry_id, title, master)],
            config_subentry_id=subentry_id,
        )


class SatelLinkMasterPanel(AlarmControlPanelEntity):
    """Arms several partitions as one, via the base integration."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_code_arm_required = True
    _attr_code_format = CodeFormat.NUMBER

    def __init__(
        self,
        entry: "SatelLinkConfigEntry",
        subentry_id: str,
        device_name: str,
        master: MasterPanel,
    ) -> None:
        self._entry = entry
        self._master = master
        self._engine = MasterEngine(None, entry, master)
        self._attr_unique_id = f"{entry.entry_id}_master_{subentry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=device_name,
            manufacturer="Satel Link Companion",
            model="Master alarm panel",
        )
        features = AlarmControlPanelEntityFeature(0)
        modes = master.modes()
        if "armed_home" in modes:
            features |= AlarmControlPanelEntityFeature.ARM_HOME
        if "armed_away" in modes:
            features |= AlarmControlPanelEntityFeature.ARM_AWAY
        if "armed_night" in modes:
            features |= AlarmControlPanelEntityFeature.ARM_NIGHT
        self._attr_supported_features = features
        self._commanded: AlarmControlPanelState = AlarmControlPanelState.DISARMED

    @property
    def extra_state_attributes(self) -> dict:
        """Show the partition sets per mode, so the config is visible."""
        m = self._master
        return {
            "home_partitions": m.home_partitions,
            "away_partitions": m.away_partitions,
            "night_partitions": m.night_partitions,
        }

    async def async_added_to_hass(self) -> None:
        # Rebind the engine to the live hass and follow the partitions so the
        # tile falls back to disarmed if they are all disarmed externally.
        self._engine = MasterEngine(self.hass, self._entry, self._master)
        entities = list(self._engine.all_partition_entities().values())
        if entities:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, entities, self._partitions_changed
                )
            )

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Last commanded state, unless every partition is disarmed."""
        if self._commanded is AlarmControlPanelState.DISARMED:
            return AlarmControlPanelState.DISARMED
        if self._all_partitions_disarmed():
            return AlarmControlPanelState.DISARMED
        return self._commanded

    def _all_partitions_disarmed(self) -> bool:
        entities = self._engine.all_partition_entities().values()
        if not entities:
            return False
        for entity_id in entities:
            state = self.hass.states.get(entity_id)
            if state is not None and state.state != AlarmControlPanelState.DISARMED:
                return False
        return True

    @callback
    def _partitions_changed(self, event) -> None:
        self.async_write_ha_state()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self._engine.async_disarm(code)
        self._commanded = AlarmControlPanelState.DISARMED
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self._arm(AlarmControlPanelState.ARMED_AWAY, "armed_away", code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        await self._arm(AlarmControlPanelState.ARMED_HOME, "armed_home", code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        await self._arm(AlarmControlPanelState.ARMED_NIGHT, "armed_night", code)

    async def _arm(
        self, target: AlarmControlPanelState, ha_state: str, code: str | None
    ) -> None:
        self._commanded = AlarmControlPanelState.ARMING
        self.async_write_ha_state()
        ok = await self._engine.async_arm(ha_state, code)
        # On failure the engine has already rolled back and fired the event.
        self._commanded = target if ok else AlarmControlPanelState.DISARMED
        self.async_write_ha_state()
