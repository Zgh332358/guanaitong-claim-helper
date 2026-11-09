"""Allow 20:30–midnight locally; reject automatic sleep/boot catch-up."""
from datetime import datetime, time
import re
import subprocess


def read_power_times():
    values = []
    for key in ("kern.boottime", "kern.waketime"):
        try:
            output = subprocess.check_output(
                ["/usr/sbin/sysctl", "-n", key], text=True,
                stderr=subprocess.DEVNULL, timeout=3,
            )
            match = re.search(r"sec\s*=\s*(\d+),\s*usec\s*=\s*(\d+)", output)
            values.append(int(match[1]) + int(match[2]) / 1_000_000 if match else None)
        except (OSError, subprocess.SubprocessError):
            values.append(None)
    return values


def claim_window_reason(now):
    # 24:00 is next day's 00:00, which falls before that day's opening time.
    return None if now.time() >= time(20, 30) else "outside_schedule_window"


def skip_reason(now, boot, wake):
    reason = claim_window_reason(now)
    if reason:
        return reason
    due = now.replace(hour=20, minute=30, second=0, microsecond=0).timestamp()
    if boot is None or wake is None:
        return "power_state_unknown"
    if boot >= due:
        return "missed_while_off"
    if wake >= due:
        return "missed_while_asleep"
    return None


def execution_guard(*, scheduled):
    reason = claim_window_reason(datetime.now())
    if reason or not scheduled:
        return reason
    boot, wake = read_power_times()
    return skip_reason(datetime.now(), boot, wake)
