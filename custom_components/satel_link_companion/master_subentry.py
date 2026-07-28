"""Satel Link Companion — config subentry flow for master alarm panels (module C).

A master panel arms several Satel partitions as one HomeKit-compatible tile.
Each mode drives its own partition set, entered as a comma-separated list in arm
order:

    Home   -> alarm_arm_home   (Satel's arm_home_mode decides the actual mode)
    Away   -> alarm_arm_away
    Night  -> alarm_arm_night

"Off" disarms every partition any mode uses, in numeric order. Leave a mode
empty to not offer it on the panel. Each master is its own config subentry, so
it becomes a device with Reconfigure / Delete.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult

from .const import SUBENTRY_TYPE_MASTER

CONF_NAME = "name"
CONF_HOME = "home_partitions"
CONF_AWAY = "away_partitions"
CONF_NIGHT = "night_partitions"


def _parse(raw: str) -> list[int] | None:
    """Comma-separated partition numbers in order, or None if malformed."""
    if not raw or not raw.strip():
        return []
    try:
        return [int(p.strip()) for p in raw.split(",") if p.strip()]
    except ValueError:
        return None


class MasterSubentryFlow(ConfigSubentryFlow):
    """Create or reconfigure a master alarm panel."""

    @property
    def _model(self) -> Any:
        entry = self._get_entry()
        runtime = getattr(entry, "runtime_data", None)
        return getattr(runtime, "model", None) if runtime else None

    def _known_partitions(self, model: Any) -> list[int]:
        return sorted({z.partition for z in model.zones if z.partition})

    def _validate(
        self, user_input: dict[str, Any], known: list[int]
    ) -> tuple[dict[str, list[int]], dict[str, str]]:
        errors: dict[str, str] = {}
        parsed: dict[str, list[int]] = {}
        for field in (CONF_HOME, CONF_AWAY, CONF_NIGHT):
            order = _parse(user_input.get(field, ""))
            if order is None or any(p not in known for p in (order or [])):
                errors[field] = "invalid_partitions"
                parsed[field] = []
            else:
                parsed[field] = order
        if not errors and not any(parsed.values()):
            errors["base"] = "no_mode"
        return parsed, errors

    def _schema(self, name: str, home: str, away: str, night: str) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=name): str,
                vol.Optional(CONF_HOME, default=home): str,
                vol.Optional(CONF_AWAY, default=away): str,
                vol.Optional(CONF_NIGHT, default=night): str,
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        model = self._model
        if model is None:
            return self.async_abort(reason="run_discovery_first")
        known = self._known_partitions(model)
        if not known:
            return self.async_abort(reason="no_partitions")

        if user_input is not None:
            parsed, errors = self._validate(user_input, known)
            if not errors:
                name = user_input.get(CONF_NAME) or "Alarm master"
                return self.async_create_entry(
                    title=name,
                    data={
                        "name": name,
                        "home_partitions": parsed[CONF_HOME],
                        "away_partitions": parsed[CONF_AWAY],
                        "night_partitions": parsed[CONF_NIGHT],
                    },
                )
            return self.async_show_form(
                step_id="user",
                data_schema=self._schema(
                    user_input.get(CONF_NAME, "Alarm master"),
                    user_input.get(CONF_HOME, ""),
                    user_input.get(CONF_AWAY, ""),
                    user_input.get(CONF_NIGHT, ""),
                ),
                errors=errors,
                description_placeholders={"partitions": ", ".join(str(p) for p in known)},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema("Alarm master", "", "", ""),
            description_placeholders={"partitions": ", ".join(str(p) for p in known)},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        model = self._model
        if model is None:
            return self.async_abort(reason="run_discovery_first")
        known = self._known_partitions(model)
        sub = self._get_reconfigure_subentry()
        data = dict(sub.data)

        if user_input is not None:
            parsed, errors = self._validate(user_input, known)
            if not errors:
                name = user_input.get(CONF_NAME) or "Alarm master"
                return self.async_update_and_abort(
                    self._get_entry(),
                    sub,
                    title=name,
                    data_updates={
                        "name": name,
                        "home_partitions": parsed[CONF_HOME],
                        "away_partitions": parsed[CONF_AWAY],
                        "night_partitions": parsed[CONF_NIGHT],
                    },
                )
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self._schema(
                    user_input.get(CONF_NAME, "Alarm master"),
                    user_input.get(CONF_HOME, ""),
                    user_input.get(CONF_AWAY, ""),
                    user_input.get(CONF_NIGHT, ""),
                ),
                errors=errors,
                description_placeholders={"partitions": ", ".join(str(p) for p in known)},
            )

        def csv(key: str) -> str:
            return ", ".join(str(p) for p in data.get(key, []))

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._schema(
                data.get("name", "Alarm master"),
                csv("home_partitions"),
                csv("away_partitions"),
                csv("night_partitions"),
            ),
            description_placeholders={"partitions": ", ".join(str(p) for p in known)},
        )


SUBENTRY_FLOWS = {SUBENTRY_TYPE_MASTER: MasterSubentryFlow}
