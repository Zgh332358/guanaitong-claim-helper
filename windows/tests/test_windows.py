import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

import dialogs
import install
import launcher
import location_access
from scheduling import ExecutionGuard, PowerState, claim_window_reason, parse_power_events, skip_reason
import task_scheduler as tasks

SID = "S-1-5-21-100-200-300-1001"


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 9, 20, 30)
        self.due = self.now.timestamp()
        self.power = PowerState(self.due - 86400, self.due - 3600, True)

    def test_window_boundaries(self):
        for value, allowed in (("20:29:59", False), ("20:30:00", True), ("21:30:00", True),
                               ("23:59:59.999999", True), ("00:00:00", False)):
            with self.subTest(value=value):
                self.assertEqual(claim_window_reason(datetime.fromisoformat("2026-11-09T" + value)) is None, allowed)

    def test_sleep_and_boot_catchup_are_rejected(self):
        self.assertEqual(skip_reason(self.now, PowerState(self.due + 1, None, True)), "missed_while_off")
        self.assertEqual(skip_reason(self.now, PowerState(self.due - 100, self.due, True)), "missed_while_asleep")

    def test_unknown_power_state_is_rejected(self):
        self.assertEqual(skip_reason(self.now, PowerState(None, None, False)), "power_state_unknown")
        self.assertEqual(skip_reason(self.now, PowerState(self.due - 10, None, True, True)), "power_state_unknown")

    def test_manual_never_reads_power(self):
        reader = MagicMock(side_effect=AssertionError("Must not read power state"))
        guard = ExecutionGuard(False, clock=lambda: self.now, power_reader=reader, ticks_reader=reader)
        self.assertIsNone(guard())
        reader.assert_not_called()

    def test_crossing_day_stops_existing_run(self):
        guard = ExecutionGuard(False, clock=lambda: self.now)
        self.now = datetime(2026, 11, 10, 20, 30)
        self.assertEqual(guard(), "outside_schedule_window")

    def test_suspend_during_run_is_detected(self):
        ticks = MagicMock(side_effect=[(100, 80), (100.01, 80.01), (120, 81)])
        reader = MagicMock(return_value=self.power)
        guard = ExecutionGuard(True, clock=lambda: self.now, power_reader=reader, ticks_reader=ticks)
        self.assertIsNone(guard())
        self.assertEqual(guard(), "resumed_during_run")
        reader.assert_called_once()

    def test_power_read_failure_stops_run(self):
        guard = ExecutionGuard(True, clock=lambda: self.now,
                               ticks_reader=MagicMock(side_effect=OSError()))
        self.assertEqual(guard(), "power_state_unknown")

    def test_event_wake_time_is_used_without_event_message(self):
        text = '''<Events><Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><System>
        <Provider Name="Microsoft-Windows-Power-Troubleshooter"/><EventID>1</EventID>
        <TimeCreated SystemTime="2026-11-09T12:31:00Z"/></System><EventData>
        <Data Name="WakeTime">2026-11-09T12:30:20Z</Data></EventData></Event></Events>'''
        state = parse_power_events(text, self.due - 86400)
        self.assertEqual(state.wake, datetime(2026, 11, 9, 12, 30, 20, tzinfo=timezone.utc).timestamp())
        self.assertTrue(state.readable)

    def test_sleep_without_resume_is_unknown(self):
        text = '''<Events><Event><System><Provider Name="Microsoft-Windows-Kernel-Power"/>
        <EventID>506</EventID><TimeCreated SystemTime="2026-11-09T12:29:00Z"/></System></Event></Events>'''
        self.assertTrue(parse_power_events(text, self.due - 86400).sleep_pending)

    def test_empty_query_is_readable_but_invalid_xml_is_not(self):
        self.assertTrue(parse_power_events("<Events/>", self.due - 86400).readable)
        with self.assertRaises(ValueError):parse_power_events("<Error/>", self.due)


class TaskXmlTests(unittest.TestCase):
    def setUp(self):
        self.root = Path("test-runtime")
        self.xml = tasks.build_task_xml(SID, self.root, datetime(2026, 11, 9, 22))
        self.task = tasks.parse_task(self.xml)

    def get(self, path):
        return self.task.findtext(path, namespaces={"t": tasks.NS})

    def test_trigger_and_no_catchup_or_wake(self):
        self.assertEqual(self.task.get("version"), "1.3")
        trigger = self.task.find("t:Triggers/t:CalendarTrigger", {"t": tasks.NS})
        self.assertEqual([node.tag.rsplit("}", 1)[-1] for node in trigger], ["Enabled", "StartBoundary", "ScheduleByDay"])
        self.assertEqual(self.get("t:Triggers/t:CalendarTrigger/t:StartBoundary"), "2026-11-09T20:30:00")
        self.assertEqual(self.get("t:Triggers/t:CalendarTrigger/t:ScheduleByDay/t:DaysInterval"), "1")
        for name in ("WakeToRun", "StartWhenAvailable", "RunOnlyIfIdle"):
            self.assertEqual(self.get("t:Settings/t:" + name), "false")
        self.assertEqual(self.get("t:Settings/t:MultipleInstancesPolicy"), "IgnoreNew")

    def test_interactive_limited_user_and_hidden_python(self):
        self.assertEqual(self.get("t:Principals/t:Principal/t:UserId"), SID)
        self.assertEqual(self.get("t:Principals/t:Principal/t:LogonType"), "InteractiveToken")
        self.assertEqual(self.get("t:Principals/t:Principal/t:RunLevel"), "LeastPrivilege")
        self.assertTrue(self.get("t:Actions/t:Exec/t:Command").endswith("pythonw.exe"))
        self.assertEqual(self.get("t:Settings/t:ExecutionTimeLimit"), "PT4M")
        tasks.assert_owned(self.task, SID, self.root)

    def test_other_user_task_is_never_overwritten(self):
        with self.assertRaises(RuntimeError):tasks.assert_owned(self.task, SID + "2", self.root)

    def test_multiple_actions_are_rejected(self):
        action = self.task.find("t:Actions", {"t": tasks.NS})
        ET.SubElement(action, "{" + tasks.NS + "}ComHandler")
        with self.assertRaises(RuntimeError):tasks.assert_owned(self.task, SID, self.root)

    def test_sid_cannot_inject_task_name(self):
        with self.assertRaises(ValueError):tasks.task_name('invalid" /F')


class LocalSafetyTests(unittest.TestCase):
    def test_location_consent_default_off_and_exact_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "consent.json"
            with patch.object(location_access, "CONSENT", file):
                self.assertFalse(location_access.location_allowed())
                location_access.set_consent(True)
                context = MagicMock()
                self.assertTrue(location_access.configure_location(context))
                context.grant_permissions.assert_called_once_with(["geolocation"], origin="https://c.guanaitong.com")
                context.set_geolocation.assert_not_called()
                location_access.set_consent(False)
                self.assertFalse(location_access.location_allowed())
                file.write_text('{"origin":"https://example.invalid","allow_real_location":true}')
                self.assertFalse(location_access.location_allowed())

    @patch("dialogs.require_windows")
    @patch("dialogs.subprocess.Popen")
    def test_native_dialog_timeout_terminates_only_its_process(self, popen, windows):
        child = popen.return_value
        child.wait.side_effect = [subprocess.TimeoutExpired("dialog", 60), 0]
        self.assertEqual(dialogs.ask("login"), "timeout")
        child.terminate.assert_called_once()

    @patch("launcher.run_native")
    @patch("launcher.subprocess.Popen")
    def test_worker_timeout_uses_its_own_pid_tree(self, popen, native):
        child = popen.return_value
        child.pid = 424242
        child.communicate.side_effect = subprocess.TimeoutExpired("worker", 120)
        native.return_value.returncode = 0
        self.assertEqual(launcher.supervise([])["status"], "execution_timeout")
        args = native.call_args.args[0]
        self.assertEqual(args[1:], ["/PID", "424242", "/T", "/F"])

    @patch("launcher.subprocess.Popen")
    def test_supervisor_drops_unknown_fields(self, popen):
        process = popen.return_value
        process.returncode = 0
        process.communicate.return_value = (json.dumps({"status":"already_claimed","clicks":1,"verified":True,
            "phase":"site_feedback","private":"do-not-export"}), None)
        value = launcher.supervise([])
        self.assertTrue(value["verified"])
        self.assertNotIn("private", value)

    @patch("launcher.subprocess.Popen")
    def test_invalid_worker_results_are_not_success(self, popen):
        process = popen.return_value
        process.returncode = 0
        process.communicate.return_value = ('{"status":"already_claimed","clicks":99,"verified":"yes"}', None)
        self.assertEqual(launcher.supervise([])["status"], "invalid_worker_result")

    @patch("launcher.open_manual")
    @patch("launcher.ask", return_value="yes")
    def test_reminder_only_opens_requested_manual_setup(self, ask, open_manual):
        launcher.remind("login_required")
        open_manual.assert_called_once_with("login.py")

    def test_shortcuts_quote_paths_and_disable_delayed_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "user&name%test%"
            source = Path(directory) / "source"
            root.mkdir(); source.mkdir()
            with patch.object(install, "ROOT", root):install.write_shortcuts(source)
            commands = list(source.glob("*.cmd"))
            self.assertEqual(len(commands), 7)
            text = (source / "立即领取.cmd").read_text()
            self.assertIn("setlocal DisableDelayedExpansion", text)
            self.assertIn('"' + str(root).replace("%", "%%"), text)
            self.assertNotIn("--scheduled", text)

    def test_unrelated_runtime_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "unrelated.txt").write_text("keep")
            with patch.object(install, "ROOT", root):
                with self.assertRaises(RuntimeError):install.check_root_owner(SID)
            self.assertEqual((root / "unrelated.txt").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
