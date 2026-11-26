"""Config and options flow for Medication Reminder."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DEFAULT_BASE_TOPIC,
    DEFAULT_COPIES,
    DEFAULT_TEMPLATE,
    DOMAIN,
    MAX_COPIES,
    OPTION_BASE_TOPIC,
    OPTION_COPIES,
    OPTION_LABEL_SIZE,
    OPTION_PRINTING_ENABLED,
    OPTION_TEMPLATE,
)
from .legacy import (
    CONF_TAKE_OVER,
    async_describe_legacy_entries,
    async_own_legacy_entries,
)

DEFAULT_TITLE = "Medication schedule"

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(OPTION_PRINTING_ENABLED, default=False): selector.BooleanSelector(),
        vol.Required(
            OPTION_BASE_TOPIC, default=DEFAULT_BASE_TOPIC
        ): selector.TextSelector(),
        vol.Required(
            OPTION_TEMPLATE, default=DEFAULT_TEMPLATE
        ): selector.TextSelector(),
        vol.Optional(OPTION_LABEL_SIZE, default=""): selector.TextSelector(),
        vol.Required(OPTION_COPIES, default=DEFAULT_COPIES): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=MAX_COPIES, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
    }
)


class MedicationReminderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create the single local Medication Reminder instance."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle setup from the integrations page."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if async_own_legacy_entries(self.hass):
            return await self.async_step_take_over()
        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_TITLE, data={})
        return self.async_show_form(step_id="user")

    async def async_step_take_over(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask whether an install from before the domain rename moves over.

        Only entries carrying this integration's own hub device are offered,
        and nothing is moved or removed unless the user picks that here.
        """
        legacy = async_own_legacy_entries(self.hass)
        # Exactly what is shown here is what a confirmation moves over.
        self._offered = [entry.entry_id for entry in legacy]
        return self.async_show_menu(
            step_id="take_over",
            menu_options=["take_over_confirm", "start_empty"],
            description_placeholders=async_describe_legacy_entries(self.hass, legacy),
        )

    async def async_step_take_over_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Set up and move the confirmed entries over on the first start."""
        still_there = {entry.entry_id for entry in async_own_legacy_entries(self.hass)}
        confirmed = [
            entry_id
            for entry_id in getattr(self, "_offered", [])
            if entry_id in still_there
        ]
        if not confirmed:
            return self.async_abort(reason="legacy_gone")
        return self.async_create_entry(
            title=DEFAULT_TITLE, data={CONF_TAKE_OVER: confirmed}
        )

    async def async_step_start_empty(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Set up without data and leave the old entries alone."""
        return self.async_create_entry(title=DEFAULT_TITLE, data={})

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow for label printing."""
        return MedicationReminderOptionsFlow()


class MedicationReminderOptionsFlow(config_entries.OptionsFlow):
    """Configure label printing over the MQTT broker Home Assistant uses."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show and store the printing options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            topic = str(user_input.get(OPTION_BASE_TOPIC, "")).strip().strip("/")
            if not topic:
                errors[OPTION_BASE_TOPIC] = "invalid_topic"
            elif any(character in topic for character in "+#"):
                # Wildcards would make us publish to a topic that cannot exist.
                errors[OPTION_BASE_TOPIC] = "invalid_topic"
            if not str(user_input.get(OPTION_TEMPLATE, "")).strip():
                errors[OPTION_TEMPLATE] = "invalid_template"
            if not errors:
                return self.async_create_entry(
                    data={
                        OPTION_PRINTING_ENABLED: bool(
                            user_input[OPTION_PRINTING_ENABLED]
                        ),
                        OPTION_BASE_TOPIC: topic,
                        OPTION_TEMPLATE: str(user_input[OPTION_TEMPLATE]).strip(),
                        OPTION_LABEL_SIZE: str(
                            user_input.get(OPTION_LABEL_SIZE, "")
                        ).strip(),
                        OPTION_COPIES: int(user_input[OPTION_COPIES]),
                    }
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, user_input or dict(self.config_entry.options)
            ),
            errors=errors,
        )
