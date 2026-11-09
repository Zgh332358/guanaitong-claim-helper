"""Windows one-shot supervisor: hidden worker, bounded cleanup and local reminders."""
import argparse
from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import subprocess
from dialogs import ask, open_manual
from settings import ROOT, require_runtime
from win_platform import hidden_options, print_status, python_exe, run_native, system_exe

FAILURES = {"execution_timeout", "worker_failed", "invalid_worker_result", "browser_or_network_error",
            "click_result_uncertain", "location_permission_required", "location_unavailable",
            "location_timeout", "unsupported_platform", "runtime_setup_required"}


def supervise(arguments, timeout=120):
    process = subprocess.Popen([python_exe(), str(Path(__file__).with_name("claim.py")), *arguments],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", errors="replace", **hidden_options())
    try:
        stdout, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        result = {"status": "execution_timeout", "clicks": None, "verified": False}
        try:
            cleanup = run_native([system_exe("taskkill.exe"), "/PID", str(process.pid), "/T", "/F"], timeout=10)
            if cleanup.returncode and process.poll() is None:
                result["error"] = "cleanup_failed"
            process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            result["error"] = "cleanup_failed"
        return result
    if process.returncode:
        return {"status": "worker_failed", "clicks": None, "verified": False}
    try:
        value = json.loads(stdout.strip())
        if not isinstance(value.get("status"), str) or not re.fullmatch(r"[a-z_]{1,64}", value["status"]):
            raise ValueError("Invalid status")
        if type(value.get("verified")) is not bool or type(value.get("clicks")) is not int or not 0 <= value["clicks"] <= 5:
            raise ValueError("Invalid result")
        result = {key: value[key] for key in ("status", "clicks", "verified")}
        for key in ("phase", "error"):
            if isinstance(value.get(key), str) and re.fullmatch(r"[a-z_]{1,64}", value[key]):
                result[key] = value[key]
        return result
    except (ValueError, KeyError, TypeError, AttributeError):
        return {"status": "invalid_worker_result", "clicks": None, "verified": False}


def remind(status):
    kind = "login" if status == "login_required" else "location" if status == "location_permission_required" else "location_error"
    try:
        answer = ask(kind)
        if answer == "yes" and kind in {"login", "location"}:
            open_manual("login.py" if kind == "login" else "location_access.py")
        return answer
    except (OSError, subprocess.SubprocessError):
        return "error"


def main():
    parser = argparse.ArgumentParser(description="Windows 关爱通后台领取")
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--no-alert", action="store_true")
    args = parser.parse_args()
    require_runtime()
    logger = logging.getLogger("gat-windows")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(ROOT / "run.log", maxBytes=262_144, backupCount=3, encoding="utf-8")
    logger.addHandler(handler)
    try:
        flags = (["--scheduled"] if args.scheduled else []) + (["--check"] if args.check else [])
        result = supervise(flags)
        result["mode"] = "check" if args.check else "scheduled" if args.scheduled else "manual"
        result["time"] = datetime.now().astimezone().isoformat(timespec="seconds")
        logger.info(json.dumps(result, ensure_ascii=False))
        print_status(json.dumps(result, ensure_ascii=False))
        if not (args.check or args.no_alert) and result["status"] in {"login_required", "location_permission_required", "location_unavailable", "location_timeout"}:
            logger.info("reminder_response=%s", remind(result["status"]))
        if result["status"] == "login_required":
            return 2
        return 1 if result["status"] in FAILURES else 0
    finally:
        handler.close()
        logger.removeHandler(handler)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError):
        print_status("运行环境不可用：请确认在 Windows 中先运行 install.cmd。")
        raise SystemExit(1)
