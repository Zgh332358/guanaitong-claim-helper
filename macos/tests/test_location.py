import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import DEFAULT, MagicMock, patch

import claim
import launcher
import location_access as location


class LocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patcher = patch.multiple(location, ROOT=self.root, CONSENT=self.root / "location-consent.json")
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_missing_or_corrupt_consent_denies(self):
        self.assertFalse(location.location_allowed())
        location.CONSENT.write_text("invalid json")
        self.assertFalse(location.location_allowed())

    def test_consent_cannot_authorize_another_origin(self):
        location.CONSENT.write_text(json.dumps({"origin": "https://example.invalid", "allow_real_location": True}))
        self.assertFalse(location.location_allowed())

    def test_authorization_is_scoped_and_contains_no_coordinates(self):
        location.set_consent(True)
        context = MagicMock()
        self.assertTrue(location.configure_location(context))
        context.grant_permissions.assert_called_once_with(["geolocation"], origin="https://c.guanaitong.com")
        context.set_geolocation.assert_not_called()
        self.assertEqual(location.CONSENT.stat().st_mode & 0o777, 0o600)
        self.assertEqual(set(json.loads(location.CONSENT.read_text())), {"origin", "allow_real_location", "updated_at"})

    def test_revoke_prevents_future_grants(self):
        location.set_consent(True)
        location.set_consent(False)
        context = MagicMock()
        self.assertFalse(location.configure_location(context))
        context.grant_permissions.assert_not_called()

    @patch("location_access.subprocess.run")
    @patch("location_access.argparse.ArgumentParser.parse_args")
    def test_cancelled_dialog_does_not_authorize(self, args, run):
        args.return_value = SimpleNamespace(revoke=False)
        run.return_value = subprocess.CompletedProcess([], 0, "button returned:取消", "")
        self.assertEqual(location.main(), 0)
        self.assertFalse(location.CONSENT.exists())

    def test_worker_does_not_click_without_consent(self):
        with patch.multiple("claim", execution_guard=DEFAULT, profile_lock=DEFAULT, sync_playwright=DEFAULT,
                            restore_state=DEFAULT, configure_location=DEFAULT, inspect_page=DEFAULT,
                            probe_real_location=DEFAULT, run_claim=DEFAULT) as mocks:
            mocks["execution_guard"].return_value = None
            mocks["configure_location"].return_value = False
            mocks["inspect_page"].return_value = ("ready", None)
            result = claim.execute(SimpleNamespace(check=False, scheduled=False))
            self.assertEqual(result.status, "location_permission_required")
            self.assertEqual(result.phase, "location_preflight")
            self.assertEqual(result.clicks, 0)
            mocks["probe_real_location"].assert_not_called()
            mocks["run_claim"].assert_not_called()

    def test_worker_does_not_click_when_real_location_unavailable(self):
        with patch.multiple("claim", execution_guard=DEFAULT, profile_lock=DEFAULT, sync_playwright=DEFAULT,
                            restore_state=DEFAULT, configure_location=DEFAULT, inspect_page=DEFAULT,
                            probe_real_location=DEFAULT, run_claim=DEFAULT) as mocks:
            mocks["execution_guard"].return_value = None
            mocks["configure_location"].return_value = True
            mocks["inspect_page"].return_value = ("ready", None)
            mocks["probe_real_location"].return_value = "location_unavailable"
            result = claim.execute(SimpleNamespace(check=False, scheduled=False))
            self.assertEqual(result.status, "location_unavailable")
            mocks["run_claim"].assert_not_called()

    @patch("launcher.subprocess.run")
    def test_location_reminder_never_starts_claim(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 0, "button returned:打开定位授权", ""),
                           subprocess.CompletedProcess([], 0, "", "")]
        self.assertTrue(launcher.remind_location("location_permission_required"))
        self.assertTrue(run.call_args.args[0][-1].endswith("授权真实定位.command"))

    def test_check_never_grants_or_probes_location(self):
        with patch.multiple("claim", execution_guard=DEFAULT, profile_lock=DEFAULT, sync_playwright=DEFAULT,
                            restore_state=DEFAULT, save_state=DEFAULT, configure_location=DEFAULT,
                            probe_real_location=DEFAULT, run_claim=DEFAULT) as mocks:
            mocks["run_claim"].return_value = claim.Outcome("ready")
            result = claim.execute(SimpleNamespace(check=True, scheduled=False))
            self.assertEqual(result.clicks, 0)
            mocks["configure_location"].assert_not_called()
            mocks["probe_real_location"].assert_not_called()

    @patch("launcher.subprocess.Popen")
    def test_supervisor_preserves_safe_diagnostics_only(self, popen):
        process = popen.return_value
        process.returncode = 0
        process.communicate.return_value = (json.dumps({"status": "click_result_uncertain", "clicks": 1,
            "verified": False, "phase": "clickability_check", "error": "pointer_intercepted", "private": "do-not-log"}), None)
        result = launcher.supervise([])
        self.assertEqual(result["phase"], "clickability_check")
        self.assertEqual(result["error"], "pointer_intercepted")
        self.assertNotIn("private", result)


if __name__ == "__main__":
    unittest.main()
