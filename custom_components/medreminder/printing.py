"""Print scan-code labels through a labelprint service on MQTT.

Jobs are published on the broker Home Assistant is already connected to, so the
integration keeps no credentials of its own. The service answers every job on
its result topic, and a print is only reported as done once that answer arrives.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    DEFAULT_BASE_TOPIC,
    DEFAULT_COPIES,
    DEFAULT_TEMPLATE,
    MAX_COPIES,
    MAX_LABEL_NAME_LENGTH,
    OPTION_BASE_TOPIC,
    OPTION_COPIES,
    OPTION_LABEL_SIZE,
    OPTION_PRINTING_ENABLED,
    OPTION_TEMPLATE,
    PRINT_RESULT_TIMEOUT,
)
from .scan_codes import SCAN_CODE_PATTERN

_LOGGER = logging.getLogger(__name__)
MQTT_DOMAIN = "mqtt"


class PrintingNotConfigured(HomeAssistantError):
    """Raised when label printing is switched off or MQTT is unavailable."""


class LabelPrinter:
    """Turn a scan code into a print job for the labelprint service."""

    def __init__(self, hass: HomeAssistant, options: dict[str, Any]) -> None:
        self.hass = hass
        self.options = dict(options or {})
        self._printing = False

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Whether the user switched label printing on."""
        return bool(self.options.get(OPTION_PRINTING_ENABLED, False))

    @property
    def base_topic(self) -> str:
        topic = str(self.options.get(OPTION_BASE_TOPIC) or "").strip().strip("/")
        return topic or DEFAULT_BASE_TOPIC

    @property
    def template(self) -> str:
        return str(self.options.get(OPTION_TEMPLATE) or "").strip() or DEFAULT_TEMPLATE

    @property
    def copies(self) -> int:
        try:
            copies = int(self.options.get(OPTION_COPIES, DEFAULT_COPIES))
        except (TypeError, ValueError):
            return DEFAULT_COPIES
        return max(1, min(MAX_COPIES, copies))

    @property
    def label_size(self) -> str:
        return str(self.options.get(OPTION_LABEL_SIZE) or "").strip()

    def mqtt_configured(self) -> bool:
        """Whether Home Assistant has an MQTT connection to publish through."""
        return bool(self.hass.config_entries.async_entries(MQTT_DOMAIN))

    def available(self) -> bool:
        """Whether a job could be published right now."""
        return self.enabled and self.mqtt_configured()

    def status(self) -> dict[str, Any]:
        """Describe label printing for the panel."""
        return {
            "enabled": self.enabled,
            "mqtt_configured": self.mqtt_configured(),
            "available": self.available(),
            "template": self.template,
            "base_topic": self.base_topic,
            "copies": self.copies,
            "label": self.label_size or None,
        }

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------

    def build_job(self, code: str, name: str) -> dict[str, Any]:
        """Build the labelprint job for one scan code."""
        if not SCAN_CODE_PATTERN.fullmatch(str(code)):
            raise ValueError("Only a Medication Reminder scan code can be printed")
        data: dict[str, Any] = {"code": str(code)}
        # The template turns the name sideways next to the code, so collapse
        # whitespace and cut what the label could not show anyway.
        label_name = " ".join(str(name or "").split())[:MAX_LABEL_NAME_LENGTH]
        if label_name:
            data["name"] = label_name
        job: dict[str, Any] = {
            "template": self.template,
            "data": data,
            "copies": self.copies,
            "job_id": f"{DOMAIN}_{uuid4().hex[:12]}",
        }
        if self.label_size:
            job["label"] = self.label_size
        return job

    async def async_print(self, code: str, name: str) -> dict[str, Any]:
        """Publish a print job and wait for the service to confirm it.

        Any user may print, so only one job runs at a time: a burst of presses
        cannot queue up labels or pile up subscriptions on the broker.
        """
        if self._printing:
            raise HomeAssistantError("A label is already being printed")
        self._printing = True
        try:
            return await self._async_print(code, name)
        finally:
            self._printing = False

    async def _async_print(self, code: str, name: str) -> dict[str, Any]:
        if not self.enabled:
            raise PrintingNotConfigured("Label printing is switched off")
        if not self.mqtt_configured():
            raise PrintingNotConfigured("MQTT is not set up in Home Assistant")
        from homeassistant.components import mqtt

        job = self.build_job(code, name)
        answer: asyncio.Future[dict[str, Any]] = self.hass.loop.create_future()

        @callback
        def handle_result(message: Any) -> None:
            if answer.done():
                return
            try:
                payload = json.loads(message.payload)
            except (TypeError, ValueError):
                return
            # Every job is answered on the same topic, so only the matching id
            # tells us about this one.
            if isinstance(payload, dict) and payload.get("job_id") == job["job_id"]:
                answer.set_result(payload)

        unsubscribe = await mqtt.async_subscribe(
            self.hass, f"{self.base_topic}/result", handle_result, qos=1
        )
        try:
            await mqtt.async_publish(
                self.hass,
                f"{self.base_topic}/print",
                json.dumps(job, ensure_ascii=False),
                qos=1,
                retain=False,
            )
            _LOGGER.debug("Sent print job %s for %s", job["job_id"], code)
            try:
                async with asyncio.timeout(PRINT_RESULT_TIMEOUT):
                    result = await answer
            except TimeoutError:
                # The job left Home Assistant; we simply never heard back.
                return {"job_id": job["job_id"], "confirmed": False}
        finally:
            unsubscribe()

        if not result.get("ok", False):
            raise HomeAssistantError(
                str(result.get("error") or "The printer rejected the job")
            )
        return {
            "job_id": job["job_id"],
            "confirmed": True,
            "bytes": result.get("bytes"),
        }
