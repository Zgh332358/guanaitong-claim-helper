"""Install a per-user LaunchAgent. Never delete login data when disabling."""
import argparse
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
from settings import ROOT

LABEL = "com.local.guanaitong-autoclaim"
PLIST = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
CODE_FILES = ["settings.py", "browser_state.py", "login.py", "scheduling.py",
              "engine.py", "claim.py", "launcher.py", "location_access.py", "install.py", "requirements.txt"]


def plist_data():
    return {
        "Label": LABEL,
        "ProgramArguments": [str(ROOT / ".venv/bin/python"), str(ROOT / "code/launcher.py"), "--scheduled"],
        "WorkingDirectory": str(ROOT / "code"),
        "StartCalendarInterval": {"Hour": 20, "Minute": 30},
        "RunAtLoad": False,
        "KeepAlive": False,
        "ProcessType": "Background",
        "LimitLoadToSessionType": "Aqua",
        "StandardOutPath": "/dev/null",
        "StandardErrorPath": "/dev/null",
        "ExitTimeOut": 10,
    }


def registered():
    return subprocess.run(["/bin/launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def check_owned_plist():
    if PLIST.exists():
        previous = plistlib.loads(PLIST.read_bytes())
        if previous.get("ProgramArguments") != plist_data()["ProgramArguments"]:
            raise RuntimeError("存在同名但内容不同的定时任务，停止安装以避免覆盖。")


def write_shortcuts(source):
    commands = {
        "重新登录.command": ["login.py"],
        "授权真实定位.command": ["location_access.py"],
        "立即领取.command": ["launcher.py"],
        "仅检查.command": ["launcher.py", "--check"],
        "停用定时.command": ["install.py", "--disable"],
    }
    for name, parts in commands.items():
        command = [str(ROOT / ".venv/bin/python"), str(ROOT / "code" / parts[0]), *parts[1:]]
        text = "#!/bin/zsh\nexec " + shlex.join(command) + "\n"
        for folder in {ROOT, source}:
            target = folder / name
            target.write_text(text, encoding="utf-8")
            target.chmod(0o700)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--disable", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise RuntimeError("本安装程序仅支持 macOS。")
    os.umask(0o077)
    check_owned_plist()
    service = f"gui/{os.getuid()}/{LABEL}"
    if args.disable:
        if registered():
            subprocess.run(["/bin/launchctl", "bootout", service], check=True)
        if PLIST.exists():
            PLIST.unlink()
        print("定时任务已停用；专用 Chrome、登录态和日志均保留。")
        return
    source = Path(__file__).resolve().parent
    uv = shutil.which("uv") or str(Path.home() / ".local/bin/uv")
    (ROOT / "code").mkdir(parents=True, exist_ok=True, mode=0o700)
    if not (ROOT / ".venv/bin/python").exists():
        subprocess.run([uv, "venv", str(ROOT / ".venv"), "--python", "3.13"], check=True)
    for name in CODE_FILES:
        destination = ROOT / "code" / name
        if (source / name).resolve() != destination.resolve():
            shutil.copy2(source / name, destination)
    subprocess.run([uv, "pip", "install", "--python", str(ROOT / ".venv/bin/python"),
                    "-r", str(ROOT / "code/requirements.txt")], check=True)
    write_shortcuts(source)
    if args.prepare_only:
        print("运行环境已准备；本次未更改定时任务的启用状态。")
        return
    if registered():
        subprocess.run(["/bin/launchctl", "bootout", service], check=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    temporary = PLIST.with_suffix(".tmp")
    temporary.write_bytes(plistlib.dumps(plist_data()))
    temporary.chmod(0o600)
    temporary.replace(PLIST)
    subprocess.run(["/bin/launchctl", "enable", service], check=True)
    subprocess.run(["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(PLIST)], check=True)
    if not registered():
        raise RuntimeError("任务未成功注册，请检查 launchctl 输出。")
    print("已启用每日本机时间 20:30 的任务；安装不会立即领取，睡眠/关机错过后不补跑。")
    print(f"日志：{ROOT / 'run.log'}")


if __name__ == "__main__":
    main()
