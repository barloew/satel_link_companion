"""Satel Link Companion — config subentry flow for links (module B, 0.2.x).

A link is a config subentry, so Home Assistant gives every link its own device
with built-in Reconfigure / Delete. There is a single "link" subentry type with
one Add button ("HA source sensor -> Satel zone"); the forwarding mode is chosen
as the first in-flow step rather than by having three separate buttons.

Steps:
    1. user        — choose how the sensor drives the zone (forwarding mode)
    2. source      — choose the Home Assistant source sensor
    3. output_zone — choose the Satel switchable output and the zone it switches
                     (plus, for the entry-delay mode, the delay; and invert /
                     minimum on-time)
    4. review      — show the coherence findings; block on errors, else create.

The chosen mode is shown in the header of every step after step 1, via a
description placeholder, so it is always clear which mode is being configured.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.helpers import selector

from .classify import output_name, zone_name
from .const import SUBENTRY_TYPE_LINK, Severity, StatusForwarding
from .i18n import render_findings

CONF_MODE = "mode"
CONF_SOURCE = "source"
CONF_OUTPUT = "output"
CONF_ZONE = "zone"
CONF_INVERT = "invert"
CONF_ENTRY_DELAY = "entry_delay_s"
CONF_MIN_ON = "min_on_s"

# Localized labels for the forwarding-mode question (step 1).
_MODE_LABELS: dict[str, dict[StatusForwarding, str]] = {
    "nl": {
        StatusForwarding.ALWAYS: "permanent",
        StatusForwarding.ARMED_ONLY: "via partitie in- / uitschakeling",
        StatusForwarding.ENTRY_DELAY: (
            "via partitie in- / uitschakeling en na in- / uitschakelvertraging"
        ),
    },
    "en": {
        StatusForwarding.ALWAYS: "Continuously (always)",
        StatusForwarding.ARMED_ONLY: "Via partition arming",
        StatusForwarding.ENTRY_DELAY: "Via partition arming — with entry/exit delay",
    },
}


class LinkSubentryFlow(ConfigSubentryFlow):
    """Create or reconfigure a link (any forwarding mode)."""

    def __init__(self) -> None:
        self._forwarding: StatusForwarding = StatusForwarding.ARMED_ONLY
        self._source: str | None = None
        self._output: int | None = None
        self._zone: int | None = None
        self._invert: bool = False
        self._entry_delay: int = 0
        self._min_on: float = 0.0

    # -- helpers ----------------------------------------------------------

    @property
    def _model(self) -> Any:
        entry = self._get_entry()
        runtime = getattr(entry, "runtime_data", None)
        return getattr(runtime, "model", None) if runtime else None

    @property
    def _lang(self) -> str:
        return self.hass.config.language

    def _mode_label(self, mode: StatusForwarding) -> str:
        table = _MODE_LABELS.get(self._lang, _MODE_LABELS["en"])
        return table.get(mode, mode.value)

    def _placeholders(self) -> dict[str, str]:
        return {"mode": self._mode_label(self._forwarding)}

    def _output_options(self, model: Any) -> list[selector.SelectOptionDict]:
        return [
            selector.SelectOptionDict(
                value=str(o.number),
                label=f"{o.number} — {o.display_name} "
                f"({output_name(o.function, self._lang)})",
            )
            for o in model.linkable_outputs()
        ]

    def _zone_options(self, model: Any) -> list[selector.SelectOptionDict]:
        return [
            selector.SelectOptionDict(
                value=str(z.number),
                label=f"{z.number} — {z.display_name} "
                f"({zone_name(z.function, self._lang)})",
            )
            for z in model.zones
        ]

    def _mode_selector(self) -> selector.SelectSelector:
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=mode.value, label=self._mode_label(mode)
                    )
                    for mode in (
                        StatusForwarding.ALWAYS,
                        StatusForwarding.ARMED_ONLY,
                        StatusForwarding.ENTRY_DELAY,
                    )
                ],
                mode=selector.SelectSelectorMode.LIST,
            )
        )

    def _existing_link_outputs(self) -> set[int]:
        out: set[int] = set()
        for sub in self._get_entry().subentries.values():
            num = sub.data.get("output_number")
            if num is not None:
                out.add(int(num))
        return out

    def _link_data(self) -> dict[str, Any]:
        return {
            "source_entity_id": self._source,
            "output_number": self._output,
            "zone_number": self._zone,
            "forwarding": self._forwarding.value,
            "invert": self._invert,
            "entry_delay_s": self._entry_delay,
            "min_on_s": self._min_on,
        }

    def _title(self) -> str:
        src = self._source or "?"
        state = self.hass.states.get(src) if src else None
        src_name = state.name if state else src
        return f"{src_name} → uitgang {self._output} → zone {self._zone}"

    # -- create: step 1 — forwarding mode ---------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        model = self._model
        if model is None:
            return self.async_abort(reason="run_discovery_first")
        if not model.linkable_outputs():
            return self.async_abort(reason="no_linkable_outputs")

        if user_input is not None:
            self._forwarding = StatusForwarding(user_input[CONF_MODE])
            return await self.async_step_source()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MODE, default=StatusForwarding.ARMED_ONLY.value
                ): self._mode_selector()
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    # -- create: step 2 — HA source sensor --------------------------------

    async def async_step_source(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            self._source = user_input[CONF_SOURCE]
            return await self.async_step_output_zone()

        schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                )
            }
        )
        return self.async_show_form(
            step_id="source",
            data_schema=schema,
            description_placeholders=self._placeholders(),
        )

    # -- create: step 3 — output + zone (+ delay / invert / min-on) -------

    async def async_step_output_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        model = self._model
        assert model is not None

        errors: dict[str, str] = {}
        if user_input is not None:
            self._output = int(user_input[CONF_OUTPUT])
            self._zone = int(user_input[CONF_ZONE])
            self._invert = bool(user_input.get(CONF_INVERT, False))
            self._min_on = float(user_input.get(CONF_MIN_ON, 0))
            if self._forwarding is StatusForwarding.ENTRY_DELAY:
                self._entry_delay = int(user_input.get(CONF_ENTRY_DELAY, 0))
            if self._output in self._existing_link_outputs():
                errors[CONF_OUTPUT] = "already_configured"
            if not errors:
                return await self.async_step_review()

        suggested = model.zone_for_output(self._output) if self._output else None
        zone_key = (
            vol.Required(CONF_ZONE, default=str(suggested))
            if suggested
            else vol.Required(CONF_ZONE)
        )
        fields: dict[Any, Any] = {
            vol.Required(CONF_OUTPUT): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._output_options(model),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            zone_key: selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._zone_options(model),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
        if self._forwarding is StatusForwarding.ENTRY_DELAY:
            fields[vol.Optional(CONF_ENTRY_DELAY, default=0)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=255, step=1, unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            )
        fields[vol.Optional(CONF_MIN_ON, default=0)] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=60, step=0.5, unit_of_measurement="s",
                mode=selector.NumberSelectorMode.BOX,
            )
        )
        fields[vol.Optional(CONF_INVERT, default=False)] = selector.BooleanSelector()

        return self.async_show_form(
            step_id="output_zone",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    # -- create: step 4 — review + create ---------------------------------

    async def async_step_review(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        model = self._model
        assert model is not None

        zone = next(z for z in model.zones if z.number == self._zone)
        output = next(o for o in model.outputs if o.number == self._output)
        findings = model.check_link(zone=zone, output=output)
        blocking = [f for f in findings if f.severity is Severity.ERROR]
        rendered = render_findings(findings, self._lang)
        placeholders = {**self._placeholders(), "findings": rendered or "—"}

        if blocking:
            if user_input is not None:
                return await self.async_step_output_zone()
            return self.async_show_form(
                step_id="review",
                data_schema=vol.Schema({}),
                errors={"base": "link_has_errors"},
                description_placeholders=placeholders,
            )

        if user_input is not None:
            return self.async_create_entry(
                title=self._title(),
                data=self._link_data(),
                unique_id=f"link_{self._output}",
            )

        return self.async_show_form(
            step_id="review",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )

    # -- reconfigure: all fields on one form -------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        model = self._model
        sub = self._get_reconfigure_subentry()
        data = dict(sub.data)

        if model is None:
            return self.async_abort(reason="run_discovery_first")

        errors: dict[str, str] = {}
        if user_input is not None:
            chosen_output = int(user_input[CONF_OUTPUT])
            taken = self._existing_link_outputs()
            current_output = data.get("output_number")
            if current_output is not None:
                taken.discard(int(current_output))
            if chosen_output in taken:
                errors[CONF_OUTPUT] = "already_configured"
            else:
                forwarding = StatusForwarding(user_input[CONF_MODE])
                updates = {
                    "source_entity_id": user_input[CONF_SOURCE],
                    "output_number": chosen_output,
                    "zone_number": int(user_input[CONF_ZONE]),
                    "forwarding": forwarding.value,
                    "invert": bool(user_input.get(CONF_INVERT, False)),
                    "min_on_s": float(user_input.get(CONF_MIN_ON, 0)),
                    "entry_delay_s": int(user_input.get(CONF_ENTRY_DELAY, 0)),
                }
                new = {**data, **updates}
                src = new["source_entity_id"]
                state = self.hass.states.get(src)
                title = (
                    f"{state.name if state else src} → uitgang "
                    f"{new['output_number']} → zone {new['zone_number']}"
                )
                return self.async_update_and_abort(
                    self._get_entry(), sub, title=title, data_updates=updates
                )

        current = StatusForwarding(data.get("forwarding", StatusForwarding.ARMED_ONLY.value))
        fields: dict[Any, Any] = {
            vol.Required(CONF_MODE, default=current.value): self._mode_selector(),
            vol.Required(
                CONF_SOURCE, default=data.get("source_entity_id")
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Required(
                CONF_OUTPUT, default=str(data.get("output_number"))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._output_options(model),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_ZONE, default=str(data.get("zone_number"))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._zone_options(model),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_ENTRY_DELAY, default=int(data.get("entry_delay_s", 0))
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=255, step=1, unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_MIN_ON, default=float(data.get("min_on_s", 0))
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=60, step=0.5, unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_INVERT, default=bool(data.get("invert", False))
            ): selector.BooleanSelector(),
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={"output": str(data.get("output_number"))},
        )


SUBENTRY_FLOWS = {SUBENTRY_TYPE_LINK: LinkSubentryFlow}
