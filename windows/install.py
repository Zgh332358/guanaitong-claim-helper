"""Windows per-user installer. Default prepares files; --enable opts into scheduling."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from settings import APP_ID, ROOT, atomic_json, require_runtime
from task_scheduler import NS, assert_owned, disable_task, enable_task, query_task, task_name
from win_platform import current_sid, print_status, require_windows, run_native, system_exe

CODE_FILES = ["settings.py", "win_platform.py", "scheduling.py", "dialogs.py", "browser_state.py",
              "engine.py", "claim.py", "login.py", "location_access.py", "launcher.py",
              "task_scheduler.py", "install.py", "requirements.txt"]


def check_root_owner(sid):
    if ROOT.is_symlink() or (hasattr(ROOT, "is_junction") and ROOT.is_junction()):
        raise RuntimeError("运行目录是链接或联接点，拒绝修改。")
    marker = ROOT / "install-info.json"
    if marker.exists():
        data = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("app_id") != APP_ID or data.get("sid") != sid:
            raise RuntimeError("已有运行目录不属于当前用户的本工具，未覆盖。")
    elif ROOT.exists() and any(ROOT.iterdir()):
        raise RuntimeError("目标目录已有未知内容，请先人工确认，不会覆盖。")


def secure_root(sid):
    ROOT.mkdir(parents=True, exist_ok=True)
    # Only this application's directory is changed, never LocalAppData itself.
    if run_native([system_exe("icacls.exe"), str(ROOT), "/reset"]).returncode:
        raise RuntimeError("未能重置本工具目录ACL，停止安装。")
    args = [system_exe("icacls.exe"), str(ROOT), "/inheritance:r", "/grant:r",
            f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"]
    if run_native(args).returncode:
        raise RuntimeError("未能设置本机目录权限，停止安装。请联系IT确认，不要绕过策略。")


def check_chrome():
    candidates = [Path(os.environ.get(key, "")) / "Google/Chrome/Application/chrome.exe"
                  for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA") if os.environ.get(key)]
    if not any(path.is_file() for path in candidates):
        raise RuntimeError("未找到 Google Chrome，请先安装到当前用户或标准系统目录。")


def write_shortcuts(source):
    commands = {
        "重新登录.cmd": ("login.py", []),
        "授权真实定位.cmd": ("location_access.py", []),
        "立即领取.cmd": ("launcher.py", []),
        "仅检查.cmd": ("launcher.py", ["--check"]),
        "启用定时.cmd": ("install.py", ["--enable"]),
        "停用定时.cmd": ("install.py", ["--disable"]),
        "查看状态.cmd": ("install.py", ["--status"]),
    }
    folders = {ROOT}
    if source.resolve() != (ROOT / "code").resolve():folders.add(source)
    for name, (script, flags) in commands.items():
        executable = str(ROOT / ".venv/Scripts/python.exe").replace("%", "%%")
        script_path = str(ROOT / "code" / script).replace("%", "%%")
        # Quote even space-free paths: Windows user names may contain cmd metacharacters.
        line = f'"{executable}" "{script_path}"' + (" " + " ".join(flags) if flags else "")
        content = "@echo off\r\nsetlocal DisableDelayedExpansion\r\nchcp 65001 >nul\r\n" + line + "\r\nset RESULT=%ERRORLEVEL%\r\necho.\r\npause\r\nexit /b %RESULT%\r\n"
        for folder in folders:(folder / name).write_bytes(content.encode("utf-8"))


def prepare(source, sid):
    check_root_owner(sid)
    check_chrome()
    uv = shutil.which("uv")
    if not uv:raise RuntimeError("未找到 uv。请先安装 uv 并重新打开终端，再运行 install.cmd。")
    secure_root(sid)
    marker = {"app_id": APP_ID, "sid": sid, "state": "preparing"}
    atomic_json(ROOT / "install-info.json", marker)
    (ROOT / "code").mkdir(exist_ok=True)
    python = ROOT / ".venv/Scripts/python.exe"
    if not python.is_file():
        subprocess.run([uv, "venv", str(ROOT / ".venv"), "--python", "3.13"], check=True, stdin=subprocess.DEVNULL)
    for name in CODE_FILES:
        target = ROOT / "code" / name
        if (source / name).resolve() != target.resolve():shutil.copy2(source / name, target)
    subprocess.run([uv, "pip", "install", "--python", str(python), "-r", str(ROOT / "code/requirements.txt")],
                   check=True, stdin=subprocess.DEVNULL)
    marker.update(state="ready", updated_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    atomic_json(ROOT / "install-info.json", marker)
    write_shortcuts(source)
    print_status("安装完成，已生成7个管理入口。本次未启用、停用或触发定时任务。")
    print_status("请先人工登录并授权真实定位，检查正常后再运行“启用定时.cmd”。")


def main():
    parser = argparse.ArgumentParser(description="Windows关爱通脚本安装器（默认仅准备文件）")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--enable", action="store_true")
    mode.add_argument("--disable", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    require_windows()
    sid = current_sid()
    if args.status:
        task = query_task(sid)
        if task is None:
            print_status("没有找到任务，或当前用户无权读取任务。")
        else:
            assert_owned(task, sid)
            enabled = task.findtext("t:Settings/t:Enabled", namespaces={"t": NS})
            print_status(json.dumps({"task": task_name(sid), "enabled": enabled == "true",
                                     "schedule": "20:30 local", "interactive_user_only": True}, ensure_ascii=False))
        return
    if args.enable or args.disable:
        require_runtime()
        check_root_owner(sid)
        if args.enable:
            enable_task(sid)
            print_status("已启用每天本机时间20:30任务；不会立即领取，不唤醒、不补跑。")
        else:
            disable_task(sid)
            print_status("已停用未来定时执行。当前已开始的任务需等待退出；账号资料和任务项保留。")
        return
    prepare(Path(__file__).resolve().parent, sid)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError, ET.ParseError) as error:
        print_status("操作未完成：" + (str(error) if isinstance(error, RuntimeError) else type(error).__name__))
        raise SystemExit(1)
