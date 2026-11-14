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
        if user_input is not None:
            return self.async_create_entry(title="Medication schedule", data={})
        return self.async_show_form(step_id="user")

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
