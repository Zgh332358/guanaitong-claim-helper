"""User-scoped Task Scheduler XML; no password logon, wake or catch-up."""
from datetime import datetime
from pathlib import PureWindowsPath
import re
import xml.etree.ElementTree as ET
from settings import APP_ID, ROOT
from win_platform import decode_output, run_native, system_exe

NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
ET.register_namespace("", NS)


def task_name(sid):
    if not re.fullmatch(r"S-1-\d+(?:-\d+)+", sid):
        raise ValueError("Invalid SID")
    return "GuanaitongAutoClaim-" + sid


def build_task_xml(sid, root=None, now=None):
    root = root or ROOT
    task_name(sid)
    now = now or datetime.now()
    task = ET.Element(f"{{{NS}}}Task", version="1.3")
    def add(parent, name, value=None, **attrs):
        node = ET.SubElement(parent, f"{{{NS}}}{name}", attrs)
        if value is not None:node.text = value
        return node
    registration = add(task, "RegistrationInfo")
    add(registration, "Description", APP_ID)
    triggers = add(task, "Triggers")
    trigger = add(triggers, "CalendarTrigger")
    add(trigger, "Enabled", "true")
    add(trigger, "StartBoundary", now.replace(hour=20, minute=30, second=0, microsecond=0).isoformat())
    add(add(trigger, "ScheduleByDay"), "DaysInterval", "1")
    principal = add(add(task, "Principals"), "Principal", id="Author")
    add(principal, "UserId", sid)
    add(principal, "LogonType", "InteractiveToken")
    add(principal, "RunLevel", "LeastPrivilege")
    settings = add(task, "Settings")
    values = {
        "MultipleInstancesPolicy": "IgnoreNew", "DisallowStartIfOnBatteries": "false",
        "StopIfGoingOnBatteries": "false", "AllowHardTerminate": "true",
        "StartWhenAvailable": "false", "RunOnlyIfNetworkAvailable": "false",
        "AllowStartOnDemand": "true", "Enabled": "true", "Hidden": "false",
        "RunOnlyIfIdle": "false", "WakeToRun": "false", "ExecutionTimeLimit": "PT4M", "Priority": "7",
    }
    for key, value in values.items():add(settings, key, value)
    action = add(add(task, "Actions", Context="Author"), "Exec")
    add(action, "Command", str(root / ".venv/Scripts/pythonw.exe"))
    add(action, "Arguments", f'"{root / "code/launcher.py"}" --scheduled')
    add(action, "WorkingDirectory", str(root / "code"))
    return ET.tostring(task, encoding="utf-16", xml_declaration=True)


def parse_task(data):
    text = re.sub(r"<\?xml[^>]*\?>", "", decode_output(data)).strip()
    return ET.fromstring(text)


def assert_owned(task, sid, root=None):
    root = root or ROOT
    get = lambda path: task.findtext(path, namespaces={"t": NS})
    expected = root / ".venv/Scripts/pythonw.exe"
    if (get("t:RegistrationInfo/t:Description") != APP_ID
            or get("t:Principals/t:Principal/t:UserId") != sid
            or get("t:Principals/t:Principal/t:LogonType") != "InteractiveToken"
            or PureWindowsPath(get("t:Actions/t:Exec/t:Command") or "") != PureWindowsPath(expected)
            or get("t:Actions/t:Exec/t:Arguments") != f'"{root / "code/launcher.py"}" --scheduled'
            or len(list(task.find("t:Actions", {"t": NS}))) != 1
            or len(task.findall("t:Actions/t:Exec", {"t": NS})) != 1):
        raise RuntimeError("存在同名但并非本工具的任务，拒绝覆盖或停用。")


def query_task(sid):
    result = run_native([system_exe("schtasks.exe"), "/Query", "/TN", task_name(sid), "/XML"])
    return parse_task(result.stdout) if result.returncode == 0 else None


def enable_task(sid):
    existing = query_task(sid)
    if existing is not None:assert_owned(existing, sid)
    path = ROOT / "task.xml"
    path.write_bytes(build_task_xml(sid))
    args = [system_exe("schtasks.exe"), "/Create", "/TN", task_name(sid), "/XML", str(path)]
    # Never force-overwrite when querying failed or an unknown task owns the name.
    if existing is not None:args.append("/F")
    result = run_native(args, timeout=30)
    if result.returncode:raise RuntimeError("任务注册失败；请检查当前用户权限或组织策略，不要绕过安全策略。")
    registered = query_task(sid)
    if registered is None:raise RuntimeError("未能读取已注册任务。")
    assert_owned(registered, sid)


def disable_task(sid):
    existing = query_task(sid)
    if existing is None:raise RuntimeError("任务不存在或当前用户无权读取，未作更改。")
    assert_owned(existing, sid)
    result = run_native([system_exe("schtasks.exe"), "/Change", "/TN", task_name(sid), "/DISABLE"])
    if result.returncode:raise RuntimeError("任务停用失败。")
