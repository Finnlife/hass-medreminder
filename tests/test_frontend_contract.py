"""Static regression tests for the panel/backend protocol contract."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[1]
PANEL = ROOT / "custom_components/medication_reminder/frontend/medication-reminder-panel.js"
WEBSOCKET = ROOT / "custom_components/medication_reminder/websocket.py"


class FrontendContractTests(unittest.TestCase):
    """Protect WebSocket IDs and explicit-only modal closing."""

    def test_domain_commands_never_reuse_websocket_id(self) -> None:
        backend = WEBSOCKET.read_text(encoding="utf-8")
        self.assertNotIn('vol.Required("id")', backend)
        for field in ("medication_id", "regimen_id", "occurrence_id"):
            self.assertIn(f'vol.Required("{field}")', backend)

    def test_frontend_sends_named_domain_ids(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        self.assertNotRegex(panel, re.compile(r'this\.call\([^\n]+\{\s*id[,}]'))
        self.assertIn("{ occurrence_id: id, minutes:", panel)
        self.assertIn("{ medication_id: id, delta:", panel)

    def test_modal_backdrop_has_no_close_action(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        self.assertNotIn('class="modal-backdrop" data-action="close-modal"', panel)
        self.assertIn('event.target.closest("button")', panel)
        self.assertNotIn('event.target.closest("button,', panel)
        self.assertGreaterEqual(panel.count('data-action="close-modal"'), 4)


if __name__ == "__main__":
    unittest.main()
