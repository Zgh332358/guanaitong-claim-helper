"""One-shot entry point: supervise the worker, log safe statuses, alert on expiry."""
import argparse
from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from settings import ROOT

LOGIN_DIALOG = '''display dialog "关爱通登录已失效。请打开专用登录窗口重新登录；登录完成后，请手动运行一次『立即领取.command』。本次不会自动重试。" with title "关爱通领取：需要登录" buttons {"稍后处理", "打开登录窗口"} default button "打开登录窗口" giving up after 60'''


def remind_login():
    try:
        result = subprocess.run(["/usr/bin/osascript", "-e", LOGIN_DIALOG],
                                capture_output=True, text=True, timeout=65)
        if result.returncode == 0 and "button returned:打开登录窗口" in result.stdout:
            subprocess.run(["/usr/bin/open", str(ROOT / "重新登录.command")],
                           check=True, timeout=5, capture_output=True)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def remind_location(status):
    if status == "location_permission_required":
        message = "领取未完成：网站要求真实定位。请先授权关爱通站点；若已授权，请检查 macOS 定位服务及 Chrome 权限。授权完成后需手动运行一次领取。不会使用虚拟坐标。"
        buttons = 'buttons {"稍后处理", "打开定位授权"} default button "打开定位授权"'
    else:
        message = "领取未完成：未能取得真实位置。请检查 macOS 定位服务、Chrome 定位权限和网络，恢复后手动运行领取。程序不会填入虚拟位置或绕过公司范围限制。"
        buttons = 'buttons {"知道了"} default button "知道了"'
    script = f'display dialog "{message}" with title "关爱通领取：定位不可用" {buttons} giving up after 60'
    try:
        result = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=65)
        if result.returncode == 0 and "button returned:打开定位授权" in result.stdout:
            subprocess.run(["/usr/bin/open", str(ROOT / "授权真实定位.command")],
                           check=True, timeout=5, capture_output=True)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def terminate_tree(pid):
    # Chrome may create its own process group; only kill descendants of this worker.
    output = subprocess.check_output(["/bin/ps", "-ax", "-o", "pid=,ppid="], text=True, timeout=5)
    edges = [tuple(map(int, line.split())) for line in output.splitlines() if line.strip()]
    owned = {pid}
    while True:
        children = {child for child, parent in edges if parent in owned}
        if children <= owned:
            break
        owned |= children
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for child in reversed(sorted(owned)):
            try:
                os.kill(child, sig)
            except ProcessLookupError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(0.3)


def supervise(arguments, timeout=120):
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("claim.py")), *arguments],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        start_new_session=True,
    )
    try:
        stdout, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_tree(process.pid)
        process.wait(timeout=5)
        return {"status": "execution_timeout", "clicks": None, "verified": False}
    if process.returncode:
        return {"status": "worker_failed", "clicks": None, "verified": False}
    try:
        result = json.loads(stdout.strip())
        safe = {key: result[key] for key in ("status", "clicks", "verified")}
        for key in ("phase", "error"):
            value = result.get(key)
            if isinstance(value, str) and len(value) <= 64 and all(c in "abcdefghijklmnopqrstuvwxyz_" for c in value):
                safe[key] = value
        return safe
    except (ValueError, KeyError, TypeError):
        return {"status": "invalid_worker_result", "clicks": None, "verified": False}


def main():
    parser = argparse.ArgumentParser(description="关爱通后台领取（不判断CPU或用户活跃度）")
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--check", action="store_true", help="只检查，不领取、不弹窗")
    parser.add_argument("--no-alert", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    logger = logging.getLogger("gat")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(ROOT / "run.log", maxBytes=262_144, backupCount=3, encoding="utf-8")
    logger.addHandler(handler)
    flags = (["--scheduled"] if args.scheduled else []) + (["--check"] if args.check else [])
    result = supervise(flags)
    result["mode"] = "check" if args.check else "scheduled" if args.scheduled else "manual"
    result["time"] = datetime.now().astimezone().isoformat(timespec="seconds")
    logger.info(json.dumps(result, ensure_ascii=False))
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] == "login_required" and not (args.check or args.no_alert):
        logger.info("login_reminder_displayed=%s", remind_login())
    if result["status"] in {"location_permission_required", "location_unavailable", "location_timeout"} and not (args.check or args.no_alert):
        logger.info("location_reminder_displayed=%s", remind_location(result["status"]))
    handler.close()
    logger.removeHandler(handler)
    if result["status"] == "login_required":
        return 2
    return 1 if result["status"] in {"execution_timeout", "worker_failed", "invalid_worker_result", "browser_or_network_error", "click_result_uncertain", "location_permission_required", "location_unavailable", "location_timeout"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
