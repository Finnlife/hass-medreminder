"""Static regression tests for the panel/backend protocol contract."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[1]
PANEL = (
    ROOT / "custom_components/medication_reminder/frontend/medication-reminder-panel.js"
)
WEBSOCKET = ROOT / "custom_components/medication_reminder/websocket.py"
STYLES = ROOT / "custom_components/medication_reminder/frontend/styles.js"


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
        self.assertIn("{ package_id: id }", panel)
        self.assertNotIn('this.call("adjust_stock"', panel)

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
            "export_history",
            "export_backup",
            "import_backup",
        ):
            self.assertIn(f'this.call("{command}"', panel)
            self.assertIn(f'{command}"', backend)
        self.assertNotIn("scanUrl(type, id)", panel)
        self.assertIn('this.call("generate_qr", { value: scanCode })', panel)
        self.assertIn("target?.scan_code", panel)
        self.assertIn("vol.Match(SCAN_CODE_PATTERN.pattern)", backend)
        self.assertIn('item.unplanned ? this.t("unplanned.history_name")', panel)

    def test_stock_badges_do_not_stretch_to_icon_height(self) -> None:
        styles = STYLES.read_text(encoding="utf-8")
        head = styles[styles.index(".med-head {") : styles.index(".med-head h3")]
        self.assertIn("align-items: flex-start", head)
        self.assertIn("justify-content: space-between", head)

    def test_background_refresh_and_toasts_preserve_form_drafts(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        # A background refresh must never replace the main area while it is
        # being typed into, and a toast must only touch the toast container.
        self.assertIn("mainHasFocus()", panel)
        self.assertIn("if (this.mainHasFocus()) return;", panel)
        show_toast = panel[
            panel.index("showToast(message") : panel.index("mainHasFocus()")
        ]
        self.assertIn("this.renderToast();", show_toast)
        self.assertNotIn("this.renderAll();", show_toast)
        self.assertNotIn("this.renderMain();", show_toast)

    def test_open_dialog_survives_background_refreshes(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        # The dialog lives in its own container that is only rebuilt when the
        # dialog identity changes, so a state refresh cannot reset its inputs.
        self.assertIn("renderOverlay(force = false)", panel)
        self.assertIn("if (!force && key === this.renderedModalKey) return;", panel)
        render_all = panel[panel.index("renderAll() {") : panel.index("renderHeader() {")]
        self.assertIn("this.renderOverlay();", render_all)
        self.assertNotIn("this.renderOverlay(true);", render_all)

    def test_delete_all_requires_explicit_confirmation(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        backend = WEBSOCKET.read_text(encoding="utf-8")
        self.assertIn('confirmation !== "DELETE"', panel)
        self.assertIn(
            'this.call("delete_all_data", { confirmation })',
            panel,
        )
        self.assertIn('vol.Required("confirmation")', backend)

    def test_medication_creation_uses_package_only_two_step_stock(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        self.assertNotIn('this.field("stock"', panel)
        self.assertNotIn('data-action="adjust-stock"', panel)
        self.assertIn("stepTwo: true", panel)
        self.assertIn("medicationId: saved.id", panel)
        self.assertIn("this.modal.stepTwo", panel)

    def test_history_export_supports_date_ranged_json_and_csv_downloads(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        backend = WEBSOCKET.read_text(encoding="utf-8")
        self.assertIn('this.call("export_history"', panel)
        self.assertIn('data-format="json"', panel)
        self.assertIn('data-format="csv"', panel)
        self.assertIn("new Blob([result.content]", panel)
        self.assertIn('vol.Required("start_date")', backend)
        self.assertIn('vol.Required("end_date")', backend)
        self.assertIn('vol.In(("json", "csv"))', backend)

    def test_full_backup_export_and_confirmed_import_are_wired(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        backend = WEBSOCKET.read_text(encoding="utf-8")
        self.assertIn('this.call("export_backup")', panel)
        self.assertIn('this.call("import_backup", { backup })', panel)
        self.assertIn('data-form="import-backup"', panel)
        self.assertIn('accept="application/json,.json"', panel)
        self.assertIn('confirm(this.t("confirm.import_backup"))', panel)
        self.assertIn('vol.Required("backup"): dict', backend)
        self.assertIn("async_import_backup", backend)


if __name__ == "__main__":
    unittest.main()
