"""Time window plus Windows power-event and in-process suspend checks."""
from dataclasses import dataclass
from datetime import datetime, time, timezone
import re
import subprocess
import xml.etree.ElementTree as ET
from win_platform import decode_output, interrupt_times, run_native, system_exe


@dataclass
class PowerState:
    boot: float | None
    wake: float | None
    readable: bool
    sleep_pending: bool = False


def claim_window_reason(now):
    return None if now.time() >= time(20, 30) else "outside_schedule_window"


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def parse_power_events(text, boot):
    text = re.sub(r"<\?xml[^>]*\?>", "", text).strip()
    if not text:
        return PowerState(boot, None, True)
    if "<!DOCTYPE" in text.upper():
        raise ValueError("Unexpected event document")
    root = ET.fromstring(text)
    if root.tag.rsplit("}", 1)[-1] not in {"Event", "Events"}:
        raise ValueError("Unexpected event root")
    events = [root] if root.tag.rsplit("}", 1)[-1] == "Event" else root.findall(".//{*}Event")
    wakes, sleeps = [], []
    for event in events:
        system = event.find("{*}System")
        provider = system.find("{*}Provider").get("Name")
        event_id = int(system.findtext("{*}EventID"))
        created = parse_time(system.find("{*}TimeCreated").get("SystemTime"))
        if provider == "Microsoft-Windows-Power-Troubleshooter" and event_id == 1:
            fields = {item.get("Name"): item.text for item in event.findall(".//{*}EventData/{*}Data")}
            wakes.append(parse_time(fields["WakeTime"]) if fields.get("WakeTime") else created)
        elif provider == "Microsoft-Windows-Kernel-Power":
            if event_id in {107, 507}:
                wakes.append(created)
            elif event_id in {42, 506}:
                sleeps.append(created)
    wake = max(wakes, default=None)
    sleep = max(sleeps, default=None)
    pending = sleep is not None and sleep >= boot and (wake is None or sleep > wake)
    return PowerState(boot, wake, True, pending)


def read_power_state():
    try:
        now = datetime.now().astimezone()
        uptime, _ = interrupt_times()
        boot = now.timestamp() - uptime
        since = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        query = ("*[System[TimeCreated[@SystemTime >= '" + since + "'] and "
                 "((Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1) or "
                 "(Provider[@Name='Microsoft-Windows-Kernel-Power'] and "
                 "(EventID=42 or EventID=107 or EventID=506 or EventID=507)))]]")
        result = run_native([system_exe("wevtutil.exe"), "qe", "System", "/q:" + query,
                             "/f:xml", "/e:Events", "/rd:true", "/c:64"], timeout=10)
        if result.returncode:
            return PowerState(None, None, False)
        return parse_power_events(decode_output(result.stdout), boot)
    except (OSError, RuntimeError, ValueError, KeyError, AttributeError, TypeError, ET.ParseError, subprocess.SubprocessError):
        return PowerState(None, None, False)


def skip_reason(now, power):
    reason = claim_window_reason(now)
    if reason:
        return reason
    if not power.readable or power.boot is None or power.sleep_pending:
        return "power_state_unknown"
    due = now.replace(hour=20, minute=30, second=0, microsecond=0).timestamp()
    if power.boot >= due:
        return "missed_while_off"
    if power.wake is not None and power.wake >= due:
        return "missed_while_asleep"
    return None


class ExecutionGuard:
    def __init__(self, scheduled, clock=None, power_reader=None, ticks_reader=None):
        self.scheduled = scheduled
        self.clock = clock or datetime.now
        self.power_reader = power_reader or read_power_state
        self.ticks_reader = ticks_reader or interrupt_times
        self.run_date = self.clock().date()
        self.power = None
        self.baseline = None

    def __call__(self):
        now = self.clock()
        if now.date() != self.run_date:
            return "outside_schedule_window"
        reason = claim_window_reason(now)
        if reason or not self.scheduled:
            return reason
        try:
            if self.baseline is None:
                self.baseline = self.ticks_reader()
            if self.power is None:
                self.power = self.power_reader()
            current = self.ticks_reader()
            slept = (current[0] - self.baseline[0]) - (current[1] - self.baseline[1])
            if slept > 0.5:
                return "resumed_during_run"
        except (OSError, RuntimeError):
            return "power_state_unknown"
        return skip_reason(self.clock(), self.power)
