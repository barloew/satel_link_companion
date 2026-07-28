"""Satel Link Companion — the forwarding engine (module B).

A link is: HA sensor -> switchable output -> zone that follows it. Since Satel
Link holds no runtime socket, "driving the output" means calling the base
integration's switch service for that output; the Satel zone then follows.

Two things decide *when* a sensor state reaches the Satel Integra Panel:

  Status forwarding — the gate:
    ALWAYS       continuously monitored (smoke/CO/gas/water) — always forward
    ARMED_ONLY   only while the zone's partition is armed
    ENTRY_DELAY  the entry/exit-zone mode. Arming opens an exit window of
                 `entry_delay_s` during which ALL motion is ignored (the output
                 is forced OFF), so you can walk out through the zone even if the
                 motion starts after arming; the forced-off then persists as long
                 as the source stays on. Afterwards a fresh violation is held
                 back for `entry_delay_s` before it is forwarded, so disarming in
                 time on entry prevents the alarm.

  Short-peak suppression — the hold:
    `min_on_s` keeps the output on at least that long after the source clears,
    so the Satel Integra Panel reliably registers a brief pulse (e.g. a PIR
    that flickers on and off within a second).

Entry delay defers turning ON; the hold defers turning OFF. Both can apply to
one link, so the per-link timing lives in a small _LinkState with its own
timers rather than in scattered callbacks.

Polarity: if the output's polarity is inverted, a violated zone corresponds to
the output being OFF. The link's `invert` flag flips the driven state so the
zone still reads correctly. (Polarity is not readable over the protocol; see
verify.py.)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .const import StatusForwarding
from .runtime import Link

if TYPE_CHECKING:
    from . import SatelLinkConfigEntry

_LOGGER = logging.getLogger(__name__)

_ARMED_STATES = {
    AlarmControlPanelState.ARMED_AWAY,
    AlarmControlPanelState.ARMED_HOME,
    AlarmControlPanelState.ARMED_NIGHT,
    AlarmControlPanelState.ARMED_VACATION,
}


class _LinkState:
    """One link plus its resolved base entities and timing state.

    `committed` is the logical "violated" state we have currently forwarded to
    the Satel Integra Panel (before the invert flip). Timers defer the
    transitions: `_entry_timer` delays committing a violation, `_hold_timer`
    delays clearing one.
    """

    __slots__ = (
        "link",
        "output_switch",
        "partition_entity",
        "committed",
        "_on_since",
        "_entry_timer",
        "_hold_timer",
        "_ignore_until_clear",
        "_exit_pending",
        "_exit_timer",
    )

    def __init__(
        self, link: Link, output_switch: str | None, partition_entity: str | None
    ) -> None:
        self.link = link
        self.output_switch = output_switch
        self.partition_entity = partition_entity
        self.committed: bool = False
        self._on_since: float = 0.0
        self._entry_timer: Callable[[], None] | None = None
        self._hold_timer: Callable[[], None] | None = None
        # Set at an arming moment for an entry/exit link: ignore motion that is
        # already present until it clears, so walking out does not start the
        # entry delay. Cleared as soon as the source reads off.
        self._ignore_until_clear: bool = False
        # The exit window right after arming: while it runs, ALL motion is
        # ignored (output forced off) so you can walk out through the zone even
        # if the motion starts after arming.
        self._exit_pending: bool = False
        self._exit_timer: Callable[[], None] | None = None

    def cancel_timers(self) -> None:
        for attr in ("_entry_timer", "_hold_timer", "_exit_timer"):
            timer = getattr(self, attr)
            if timer is not None:
                timer()
                setattr(self, attr, None)

    def clear_entry_timer(self) -> None:
        if self._entry_timer is not None:
            self._entry_timer()
            self._entry_timer = None

    def clear_hold_timer(self) -> None:
        if self._hold_timer is not None:
            self._hold_timer()
            self._hold_timer = None

    def mark_committed(self, violated: bool) -> None:
        self.committed = violated
        if violated:
            self._on_since = time.monotonic()

    def hold_remaining(self) -> float:
        """Seconds the output must still stay on to satisfy min_on_s."""
        if self.link.min_on_s <= 0:
            return 0.0
        return max(0.0, self._on_since + self.link.min_on_s - time.monotonic())


class LinkEngine:
    """Watches source sensors and mirrors them onto Satel outputs."""

    def __init__(self, hass: HomeAssistant, entry: "SatelLinkConfigEntry") -> None:
        self._hass = hass
        self._entry = entry
        self._states: list[_LinkState] = []
        self._unsubscribe: list[Callable[[], None]] = []

    async def async_start(self) -> None:
        runtime = self._entry.runtime_data
        if runtime.base is None:
            _LOGGER.warning("Link engine idle: no base integration resolved")
            return

        outputs = runtime.base.by_number("output")
        partitions = runtime.base.by_number("partition")
        zones = {z.number: z for z in runtime.model.zones} if runtime.model else {}

        watched: set[str] = set()
        for link in runtime.links:
            output = outputs.get(link.output_number)
            zone = zones.get(link.zone_number)
            partition = zone.partition if zone else None
            part_entity = (
                partitions[partition].entity_id if partition in partitions else None
            )
            state = _LinkState(
                link=link,
                output_switch=output.entity_id if output else None,
                partition_entity=part_entity,
            )
            self._states.append(state)

            if state.output_switch is None:
                _LOGGER.warning(
                    "Link on output %d has no switch in the base integration; "
                    "expose it there first",
                    link.output_number,
                )
                continue

            watched.add(link.source_entity_id)
            if part_entity:
                watched.add(part_entity)

        if watched:
            self._unsubscribe.append(
                async_track_state_change_event(
                    self._hass, list(watched), self._handle_change
                )
            )
        # Sync once to reality; startup skips the entry delay (it is not a fresh
        # entry event) but honours the gate. Entry/exit links treat startup like
        # an arming moment — they start at rest and ignore motion already present
        # — so a restart while armed can never instantly alarm an entry zone.
        for state in self._states:
            if state.output_switch is None:
                continue
            if state.link.forwarding is StatusForwarding.ENTRY_DELAY:
                state._ignore_until_clear = True
            self._evaluate(state, initial=True)

    async def async_stop(self) -> None:
        for unsub in self._unsubscribe:
            unsub()
        self._unsubscribe.clear()
        for state in self._states:
            state.cancel_timers()

    @callback
    def _handle_change(self, event: Event[EventStateChangedData]) -> None:
        # not_from / no not_to (see satel_output_mapping rev. 6):
        # A source RECOVERING from unavailable/unknown is not a fresh detection,
        # so a reconnect that lands on 'on' must not raise the output. We skip
        # re-evaluating that source's link on such an edge. A source GOING to
        # unavailable/unknown is NOT skipped: it falls through to _wants (source
        # no longer 'on') and drives the output OFF — the fail-silent rest state.
        # Gate (partition) changes are never a source edge, so never skipped.
        entity_id = event.data["entity_id"]
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        from_unavailable = old is None or old.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        )
        # Arming edge: a partition entity entering an armed state. An entry/exit
        # (ENTRY_DELAY) link then forces OFF and ignores motion already present
        # (you walking out) until it clears, so only a fresh violation after
        # arming starts the entry delay.
        arming = (
            new is not None
            and new.state in _ARMED_STATES
            and (old is None or old.state not in _ARMED_STATES)
        )
        for state in self._states:
            if state.output_switch is None:
                continue
            if entity_id == state.link.source_entity_id and from_unavailable:
                continue
            if (
                arming
                and entity_id == state.partition_entity
                and state.link.forwarding is StatusForwarding.ENTRY_DELAY
            ):
                # Arming an entry/exit zone: force OFF and open the exit window.
                # During the window ALL motion is ignored (walking out), and the
                # forced-off then persists as long as the source stays on.
                state.cancel_timers()
                state._ignore_until_clear = True
                self._commit(state, False)
                if state.link.entry_delay_s > 0:
                    state._exit_pending = True
                    state._exit_timer = async_call_later(
                        self._hass,
                        state.link.entry_delay_s,
                        self._exit_elapsed(state),
                    )
                continue
            self._evaluate(state)

    @callback
    def _evaluate(self, state: _LinkState, *, initial: bool = False) -> None:
        """Bring the committed (logical) state toward what the source wants,
        applying the entry delay on the way up and the hold on the way down."""
        if initial:
            # At startup drive the output to match reality, even if the logical
            # state already "matches" — the physical output (with invert) has
            # not been set yet. No entry delay, no hold.
            self._commit(state, self._wants(state))
            return

        want_violated = self._wants(state)

        if want_violated == state.committed:
            state.clear_entry_timer()  # target reached; drop any pending rise
            return

        if want_violated:
            self._rise(state, initial=initial)
        else:
            self._fall(state)

    def _wants(self, state: _LinkState) -> bool:
        """True when the source is on and the gate is open.

        Two suppressions keep an entry/exit link at rest around arming:
        `_exit_pending` — the exit window right after arming — ignores ALL
        motion (you walking out, even if it starts after arming); once that
        window ends, `_ignore_until_clear` keeps the link at rest as long as the
        source is still on, so only a fresh violation after you have left starts
        the entry delay.
        """
        source = self._hass.states.get(state.link.source_entity_id)
        source_on = source is not None and source.state == STATE_ON
        if state._exit_pending:
            return False
        if state._ignore_until_clear:
            if not source_on:
                state._ignore_until_clear = False
            return False
        return source_on and self._gate_open(state)

    def _rise(self, state: _LinkState, *, initial: bool) -> None:
        """Source wants a violation. Commit now, unless an entry delay applies."""
        link = state.link
        state.clear_hold_timer()
        if not initial and link.forwarding is StatusForwarding.ENTRY_DELAY and (
            link.entry_delay_s > 0
        ):
            if state._entry_timer is None:
                state._entry_timer = async_call_later(
                    self._hass, link.entry_delay_s, self._entry_elapsed(state)
                )
            return
        self._commit(state, True)

    def _fall(self, state: _LinkState) -> None:
        """Source cleared. Cancel a pending rise; honour the minimum on-time."""
        state.clear_entry_timer()
        remaining = state.hold_remaining()
        if remaining > 0:
            if state._hold_timer is None:
                state._hold_timer = async_call_later(
                    self._hass, remaining, self._hold_elapsed(state)
                )
            return
        self._commit(state, False)

    def _entry_elapsed(self, state: _LinkState) -> Callable:
        @callback
        def _fire(_now) -> None:
            state._entry_timer = None
            # The delay is over: forward the violation only if it still stands.
            if self._wants(state) and not state.committed:
                self._commit(state, True)

        return _fire

    def _hold_elapsed(self, state: _LinkState) -> Callable:
        @callback
        def _fire(_now) -> None:
            state._hold_timer = None
            self._evaluate(state)

        return _fire

    def _exit_elapsed(self, state: _LinkState) -> Callable:
        @callback
        def _fire(_now) -> None:
            state._exit_timer = None
            state._exit_pending = False
            # Exit window over: re-evaluate. If the source is still on, the
            # _ignore_until_clear flag (set at arming) keeps the link at rest
            # until it clears; only a fresh violation after that starts the
            # entry delay.
            self._evaluate(state)

        return _fire

    def _commit(self, state: _LinkState, violated: bool) -> None:
        state.mark_committed(violated)
        output_active = violated ^ state.link.invert
        current = self._hass.states.get(state.output_switch)
        if current is not None and (current.state == STATE_ON) == output_active:
            return
        self._hass.async_create_task(
            self._hass.services.async_call(
                "switch",
                "turn_on" if output_active else "turn_off",
                {"entity_id": state.output_switch},
                blocking=False,
            )
        )

    def _gate_open(self, state: _LinkState) -> bool:
        forwarding = state.link.forwarding
        if forwarding is StatusForwarding.ALWAYS:
            return True
        if state.partition_entity is None:
            return False
        panel = self._hass.states.get(state.partition_entity)
        return panel is not None and panel.state in _ARMED_STATES
