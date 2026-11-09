import unittest
from datetime import datetime
from unittest.mock import patch

import scheduling
from scheduling import skip_reason


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.due = datetime(2026, 11, 5, 20, 30).timestamp()
        self.boot = self.due - 86400
        self.wake = self.due - 3600

    def reason(self, seconds, boot=None, wake=None):
        now = datetime.fromtimestamp(self.due + seconds)
        return skip_reason(now, self.boot if boot is None else boot,
                           self.wake if wake is None else wake)

    def test_awake_at_due(self):
        self.assertIsNone(self.reason(0))

    def test_late_start_and_clicks_are_allowed_until_midnight(self):
        for seconds in (61, 121, 1800, 3600, 12599):
            with self.subTest(seconds=seconds):
                self.assertIsNone(self.reason(seconds))

    def test_last_microsecond_before_midnight_is_allowed(self):
        self.assertIsNone(skip_reason(datetime(2026, 11, 5, 23, 59, 59, 999999), self.boot, self.wake))

    def test_before_start_is_rejected(self):
        self.assertEqual(self.reason(-0.000001), "outside_schedule_window")

    def test_midnight_and_next_morning_are_rejected(self):
        self.assertEqual(self.reason(12600), "outside_schedule_window")
        self.assertEqual(self.reason(12601), "outside_schedule_window")
        self.assertEqual(self.reason(12600 + 8 * 3600), "outside_schedule_window")

    def test_next_evening_has_its_own_window(self):
        self.assertIsNone(self.reason(86400))

    def test_sleep_and_boot_catchup_are_still_skipped(self):
        self.assertEqual(self.reason(1800, wake=self.due + 10), "missed_while_asleep")
        self.assertEqual(self.reason(1800, boot=self.due + 10), "missed_while_off")

    def test_resume_during_execution_is_skipped(self):
        self.assertEqual(self.reason(80, wake=self.due + 70), "missed_while_asleep")

    def test_missing_power_state_fails_closed(self):
        self.assertEqual(skip_reason(datetime.fromtimestamp(self.due), None, self.wake),
                         "power_state_unknown")

    @patch("scheduling.read_power_times")
    @patch("scheduling.datetime")
    def test_manual_mode_does_not_read_power_state(self, clock, power):
        clock.now.return_value = datetime(2026, 11, 5, 23, 30)
        self.assertIsNone(scheduling.execution_guard(scheduled=False))
        power.assert_not_called()

    @patch("scheduling.read_power_times")
    @patch("scheduling.datetime")
    def test_manual_mode_rejects_before_start(self, clock, power):
        clock.now.return_value = datetime(2026, 11, 5, 20, 29, 59)
        self.assertEqual(scheduling.execution_guard(scheduled=False), "outside_schedule_window")
        power.assert_not_called()

    @patch("scheduling.read_power_times")
    @patch("scheduling.datetime")
    def test_automatic_mode_keeps_power_guard(self, clock, power):
        clock.now.return_value = datetime(2026, 11, 5, 23, 30)
        power.return_value = [self.boot, self.due + 10]
        self.assertEqual(scheduling.execution_guard(scheduled=True), "missed_while_asleep")
        power.assert_called_once()


if __name__ == "__main__":
    unittest.main()
