"""Satel Link Companion — config and options flow.

Flow shape:

    1. user step         — confirm we found a base integration (satel_integra /
                           ha_satel_integra_ext) and adopt its host/port/code.
    2. discover step     — run the one-off Satel Integra Panel scan. This briefly unloads the
                           base integration (the ETHM allows one client), scans,
                           and reloads it. Result is cached on the entry.
    3. create entry      — the merged model is stored; entities and links are
                           configured afterwards from the options flow.

Modules and links are added from the options flow, which is where the reviewers'
"modular, meet the user where they are" requirement lives: linking a sensor,
adopting a cover, or exposing an output as a switch are independent steps.

Nothing here holds a rendered sentence: user-facing text comes from
translations/<lang>.json via the standard HA config-flow mechanism (step ids and
error keys), and finding/remedy keys from classify/verify.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DEFAULT_PORT, DOMAIN, StatusForwarding
from .model import SystemModel
from .registry import ExistingConfig
from .registry_ha import find_base_entry, read_existing
from .runtime import (
    OPT_MODEL,
    OPT_SETTINGS,
    Settings,
    dump_model,
    load_model,
    load_settings,
)

_LOGGER = logging.getLogger(__name__)

CONF_BASE_ENTRY = "base_entry_id"

# Field names used in the link/control subflow forms.
CONF_OUTPUT = "output"
CONF_ZONE = "zone"
CONF_SOURCE = "source"
CONF_FORWARDING = "forwarding"
CONF_INVERT = "invert"
CONF_ENTRY_DELAY = "entry_delay_s"
CONF_MIN_ON = "min_on_s"
CONF_LOOKBACK = "breach_lookback_s"
CONF_MASTER_NAME = "name"
CONF_MASTER_PARTITIONS = "partitions"
CONF_CONFIRM = "confirm"


class SatelLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up Satel Link Companion on top of an existing Satel base integration."""

    VERSION = 4

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Link, control and master subentries: one Add button + device each."""
        from .control_subentry import SUBENTRY_FLOWS as CONTROL_FLOWS
        from .link_subentry import SUBENTRY_FLOWS as LINK_FLOWS
        from .master_subentry import SUBENTRY_FLOWS as MASTER_FLOWS

        return {**LINK_FLOWS, **CONTROL_FLOWS, **MASTER_FLOWS}

    def __init__(self) -> None:
        self._existing: ExistingConfig | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Adopt a base integration, or fall back to manual connection details."""
        base_entry = find_base_entry(self.hass)

        if base_entry is None:
            return await self.async_step_manual()

        self._existing = read_existing(self.hass, base_entry)

        if user_input is not None:
            await self.async_set_unique_id(f"{DOMAIN}_{base_entry.entry_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Satel Link Companion",
                data={
                    CONF_BASE_ENTRY: base_entry.entry_id,
                    CONF_HOST: self._existing.host,
                    CONF_PORT: self._existing.port,
                    CONF_CODE: self._existing.code,
                },
            )

        # Show what we will adopt; text is in translations under step "user".
        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "base_domain": base_entry.domain,
                "host": self._existing.host or "?",
                "zones": str(len(self._existing.zones)),
                "outputs": str(len(self._existing.outputs)),
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """No base integration found: ask for connection details directly."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{DOMAIN}_{user_input[CONF_HOST]}_{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Satel Link Companion",
                data={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_CODE: user_input.get(CONF_CODE),
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_CODE): str,
            }
        )
        return self.async_show_form(
            step_id="manual", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return SatelLinkOptionsFlow(entry)


class SatelLinkOptionsFlow(OptionsFlow):
    """Modular configuration: discovery, links, controls — each independent."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        # Selection state, carried across the steps of one subflow.
        self._sel_output: int | None = None
        self._sel_zone: int | None = None
        self._sel_source: str | None = None
        self._sel_forwarding: StatusForwarding | None = None
        self._sel_invert: bool = False
        self._sel_entry_delay: int = 0
        self._sel_min_on: float = 0.0

    @property
    def _model(self) -> SystemModel | None:
        """The discovered model: freshest from runtime_data, else from options.

        Persisted in options by the discover step, so links and controls can be
        configured after a restart without re-scanning the Satel Integra Panel.
        """
        runtime = getattr(self._entry, "runtime_data", None)
        if runtime is not None and getattr(runtime, "model", None) is not None:
            return runtime.model
        stored = self._entry.options.get(OPT_MODEL)
        return load_model(stored) if stored else None

    @property
    def _language(self) -> str:
        return self.hass.config.language

    def _options_with(self, **changes: Any) -> dict[str, Any]:
        """Current options plus changes, so we never drop links/controls/model."""
        return {**self._entry.options, **changes}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Menu of independent modules (translations key: 'options.step.init')."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "discover",   # 1 — inventory the Satel Integra structure
                "settings",   # 10 — breach watch window
            ],
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Module A — run the one-off scan.

        The scan needs the integration socket, which the base integration holds
        (the ETHM allows one client). So: unload base -> scan -> reload base.
        Confirmed by the user before we interrupt their alarm connection.
        """
        if user_input is None:
            return self.async_show_form(step_id="discover")

        from .discovery_runner import run_discovery  # local import: pulls HA + lib

        try:
            model = await run_discovery(self.hass, self._entry)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Discovery failed")
            return self.async_show_form(
                step_id="discover", errors={"base": "discovery_failed"}
            )

        # Persist the full model so links/controls survive a restart without a
        # re-scan. Existing links/controls are kept intact.
        if (runtime := getattr(self._entry, "runtime_data", None)) is not None:
            runtime.model = model
        return self.async_create_entry(
            title="", data=self._options_with(**{OPT_MODEL: dump_model(model)})
        )

    # -- Module D: breach lookback settings --------------------------------

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set the breach lookback window: system-wide, with a per-partition
        override. The window is how many seconds back the breach snapshot
        looks when a partition is triggered."""
        settings = load_settings(self._entry.options)
        model = self._model
        partitions = (
            sorted({z.partition for z in model.zones if z.partition})
            if model
            else []
        )

        if user_input is not None:
            overrides: dict[int, float] = {}
            for number in partitions:
                value = user_input.get(f"lookback_p{number}")
                if value is not None:
                    overrides[number] = float(value)
            new_settings = Settings(
                breach_lookback_s=float(user_input[CONF_LOOKBACK]),
                partition_lookback=overrides,
            )
            return self.async_create_entry(
                title="",
                data=self._options_with(**{OPT_SETTINGS: new_settings.to_dict()}),
            )

        fields: dict[Any, Any] = {
            vol.Required(
                CONF_LOOKBACK, default=settings.breach_lookback_s
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=120, step=0.5, unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            )
        }
        # One optional override field per partition; blank = use the default.
        for number in partitions:
            key = f"lookback_p{number}"
            override = settings.partition_lookback.get(number)
            field = (
                vol.Optional(key, default=override)
                if override is not None
                else vol.Optional(key)
            )
            fields[field] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=120, step=0.5, unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            )
        return self.async_show_form(
            step_id="settings", data_schema=vol.Schema(fields)
        )
