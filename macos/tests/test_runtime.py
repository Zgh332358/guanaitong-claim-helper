import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import DEFAULT, MagicMock, patch

import browser_state
import claim
import launcher
from install import plist_data
from settings import profile_lock


class RuntimeTests(unittest.TestCase):
    def test_launchagent_is_daily_without_keepalive_or_runatload(self):
        data = plistlib.loads(plistlib.dumps(plist_data()))
        self.assertEqual(data["StartCalendarInterval"], {"Hour": 20, "Minute": 30})
        self.assertFalse(data["KeepAlive"])
        self.assertFalse(data["RunAtLoad"])
        self.assertEqual(data["ProgramArguments"][-1], "--scheduled")
        self.assertNotIn("Desktop", data["WorkingDirectory"])

    def test_profile_lock_prevents_concurrent_login_and_claim(self):
        with tempfile.TemporaryDirectory() as root:
            with profile_lock(Path(root)):
                with self.assertRaises(RuntimeError):
                    with profile_lock(Path(root)):
                        self.fail("Second process should not obtain the profile lock")
            with profile_lock(Path(root)):
                pass

    def test_auth_snapshot_is_private_and_restores_session_cookies(self):
        context = MagicMock()
        # Synthetic test values only; no access to the real authentication file.
        context.storage_state.return_value = {"cookies": [{"name": "fixture", "value": "test-only"}], "origins": []}
        context.pages = []
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "auth.json"
            with patch.object(browser_state, "STATE", state):
                browser_state.save_state(context)
                self.assertEqual(state.stat().st_mode & 0o777, 0o600)
                self.assertEqual(json.loads(state.read_text())["sessionStorage"], {})
                browser_state.restore_state(context)
                context.add_cookies.assert_called_once_with(context.storage_state.return_value["cookies"])
                context.add_init_script.assert_called_once()

    @patch("launcher.subprocess.run")
    def test_login_popup_only_opens_login_when_user_chooses(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "button returned:稍后处理, gave up:false", "")
        self.assertTrue(launcher.remind_login())
        self.assertEqual(run.call_count, 1)
        self.assertIn("手动运行一次", run.call_args.args[0][-1])

    @patch("launcher.subprocess.run")
    def test_popup_can_open_manual_login_but_never_claims(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 0, "button returned:打开登录窗口, gave up:false", ""),
                           subprocess.CompletedProcess([], 0, "", "")]
        self.assertTrue(launcher.remind_login())
        self.assertTrue(run.call_args.args[0][-1].endswith("重新登录.command"))
        self.assertEqual(run.call_count, 2)

    @patch("launcher.subprocess.run")
    def test_popup_timeout_is_bounded(self, run):
        run.side_effect = subprocess.TimeoutExpired("osascript", 65)
        self.assertFalse(launcher.remind_login())

    @patch("claim.sync_playwright")
    @patch("claim.execution_guard", return_value="outside_schedule_window")
    def test_outside_window_never_starts_browser(self, guard, browser):
        for scheduled in (False, True):
            result = claim.execute(SimpleNamespace(scheduled=scheduled, check=False))
            self.assertEqual(result.status, "outside_schedule_window")
            guard.assert_called_with(scheduled=scheduled)
        browser.assert_not_called()

    def test_read_only_check_bypasses_time_guard(self):
        with patch.multiple("claim", execution_guard=DEFAULT, profile_lock=DEFAULT,
                            sync_playwright=DEFAULT, restore_state=DEFAULT,
                            save_state=DEFAULT, run_claim=DEFAULT) as mocks:
            mocks["run_claim"].return_value = claim.Outcome("ready")
            result = claim.execute(SimpleNamespace(scheduled=False, check=True))
            options = mocks["run_claim"].call_args.kwargs
            self.assertTrue(options["check"])
            self.assertIsNone(options["guard"]())
            mocks["execution_guard"].assert_not_called()
            self.assertEqual(result.clicks, 0)

    def test_manual_run_rechecks_window_during_execution(self):
        with patch.multiple("claim", execution_guard=DEFAULT, profile_lock=DEFAULT,
                            sync_playwright=DEFAULT, restore_state=DEFAULT,
                            save_state=DEFAULT, run_claim=DEFAULT) as mocks:
            mocks["execution_guard"].side_effect = [None, "outside_schedule_window"]
            mocks["run_claim"].side_effect = lambda page, **kw: claim.Outcome(kw["guard"]())
            result = claim.execute(SimpleNamespace(scheduled=False, check=False))
            self.assertEqual(result.status, "outside_schedule_window")
            self.assertEqual(mocks["execution_guard"].call_count, 2)
            mocks["execution_guard"].assert_called_with(scheduled=False)

    @patch("launcher.terminate_tree")
    @patch("launcher.subprocess.Popen")
    def test_worker_timeout_triggers_cleanup(self, popen, terminate):
        process = popen.return_value
        process.communicate.side_effect = subprocess.TimeoutExpired("worker", 120)
        process.pid = 123456
        self.assertEqual(launcher.supervise([])["status"], "execution_timeout")
        terminate.assert_called_once_with(123456)
        process.wait.assert_called_once_with(timeout=5)


if __name__ == "__main__":
    unittest.main()
