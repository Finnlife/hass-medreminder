"""Static regression tests for the panel/backend protocol contract."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[1]
PANEL = (
    ROOT / "custom_components/medication_reminder/frontend/medication-reminder-panel.js"
)
WEBSOCKET = ROOT / "custom_components/medication_reminder/websocket.py"


class FrontendContractTests(unittest.TestCase):
    """Protect WebSocket IDs and explicit-only modal closing."""

    def test_domain_commands_never_reuse_websocket_id(self) -> None:
        backend = WEBSOCKET.read_text(encoding="utf-8")
        self.assertNotIn('vol.Required("id")', backend)
        for field in ("medication_id", "package_id", "regimen_id", "occurrence_id"):
            self.assertIn(f'vol.Required("{field}")', backend)

    def test_snooze_command_still_calls_manager(self) -> None:
        backend = WEBSOCKET.read_text(encoding="utf-8")
        start = backend.index("async def ws_snooze")
        end = backend.index("async def ws_postpone_interval")
        snooze_handler = backend[start:end]
        self.assertIn("async_snooze", snooze_handler)
        self.assertIn('msg["occurrence_id"]', snooze_handler)

    def test_frontend_sends_named_domain_ids(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        self.assertNotRegex(panel, re.compile(r"this\.call\([^\n]+\{\s*id[,}]"))
        self.assertIn("{ occurrence_id: id, minutes:", panel)
        self.assertIn("{ medication_id: id, delta:", panel)
        self.assertIn("{ package_id: id }", panel)

    def test_modal_backdrop_has_no_close_action(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        self.assertNotIn('class="modal-backdrop" data-action="close-modal"', panel)
        self.assertIn('event.target.closest("button")', panel)
        self.assertNotIn('event.target.closest("button,', panel)
        self.assertGreaterEqual(panel.count('data-action="close-modal"'), 4)

    def test_new_product_flows_are_wired_end_to_end(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        backend = WEBSOCKET.read_text(encoding="utf-8")
        for command in (
            "save_package",
            "delete_package",
            "record_unplanned_intake",
            "postpone_interval",
            "generate_qr",
        ):
            self.assertIn(f'this.call("{command}"', panel)
            self.assertIn(f'{command}"', backend)
        self.assertNotIn("scanUrl(type, id)", panel)
        self.assertIn('this.call("generate_qr", { value: scanCode })', panel)
        self.assertIn("target?.scan_code", panel)
        self.assertIn('item.unplanned ? this.t("unplanned.history_name")', panel)

    def test_stock_badges_do_not_stretch_to_icon_height(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        self.assertIn(
            ".stock-top{display:flex;align-items:flex-start;justify-content:space-between}",
            panel,
        )

    def test_background_refresh_and_toasts_preserve_form_drafts(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        self.assertIn("(!showSpinner && this.hasActiveDraft())", panel)
        self.assertIn(
            "if (showSpinner || !this.hasActiveDraft()) this.render();", panel
        )
        self.assertIn("this.renderToastOnly();", panel)
        show_toast = panel[
            panel.index("showToast(message") : panel.index("medication(id)")
        ]
        self.assertNotIn("this.render();", show_toast)

    def test_delete_all_requires_explicit_confirmation(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        backend = WEBSOCKET.read_text(encoding="utf-8")
        self.assertIn('confirmation !== "DELETE"', panel)
        self.assertIn(
            'this.call("delete_all_data", { confirmation })',
            panel,
        )
        self.assertIn('vol.Required("confirmation")', backend)


if __name__ == "__main__":
    unittest.main()
