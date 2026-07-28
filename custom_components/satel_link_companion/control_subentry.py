"""Satel Link Companion — config subentry flow for roller-shutter covers (module B2).

The base integration already exposes switchable outputs as switches and
read-only outputs as binary sensors, so Satel Link Companion does NOT duplicate those.
The one thing the base cannot do is bundle a roller-shutter's two outputs
(up + down) into a single cover — that is the value this subentry adds.

Each cover is a config subentry, so it gets its own device with a built-in
Delete. The flow is a single step: pick the roller-shutter pair. Driving still
happens through the base integration's up/down switches; Satel Link Companion holds no
runtime socket.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.helpers import selector

from .const import HaPlatform, SUBENTRY_TYPE_CONTROL

CONF_TARGET = "target"


class ControlSubentryFlow(ConfigSubentryFlow):
    """Create a roller-shutter cover from a Satel output pair."""

    @property
    def _model(self) -> Any:
        entry = self._get_entry()
        runtime = getattr(entry, "runtime_data", None)
        return getattr(runtime, "model", None) if runtime else None

    def _options(self, model: Any) -> list[selector.SelectOptionDict]:
        return [
            selector.SelectOptionDict(
                value=str(c.number),
                label=f"{c.name} (uitgangen {c.up.number}/{c.down.number})",
            )
            for c in model.covers
        ]

    def _existing_outputs(self) -> set[int]:
        out: set[int] = set()
        for sub in self._get_entry().subentries.values():
            if sub.subentry_type == SUBENTRY_TYPE_CONTROL:
                num = sub.data.get("output_number")
                if num is not None:
                    out.add(int(num))
        return out

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        model = self._model
        if model is None:
            return self.async_abort(reason="run_discovery_first")
        options = self._options(model)
        if not options:
            return self.async_abort(reason="no_shutters")

        errors: dict[str, str] = {}
        if user_input is not None:
            number = int(user_input[CONF_TARGET])
            if number in self._existing_outputs():
                errors[CONF_TARGET] = "already_configured"
            else:
                cover = next(c for c in model.covers if c.number == number)
                data = {
                    "output_number": cover.up.number,
                    "platform": HaPlatform.COVER.value,
                    "down_number": cover.down.number,
                }
                title = (
                    f"{cover.name} (rolluik {cover.up.number}/{cover.down.number})"
                )
                return self.async_create_entry(
                    title=title, data=data, unique_id=f"control_{cover.up.number}"
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_TARGET): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )


SUBENTRY_FLOWS = {SUBENTRY_TYPE_CONTROL: ControlSubentryFlow}
