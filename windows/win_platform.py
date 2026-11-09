"""Windows-only native helpers. No stored passwords and no system policy changes."""
import ctypes
import os
from pathlib import Path
import re
import subprocess
import sys


class UnsupportedPlatform(RuntimeError):
    pass


def require_windows():
    if sys.platform != "win32":
        raise UnsupportedPlatform("此版本仅支持 Windows 10/11，请勿在 macOS 上运行入口。")


def hidden_options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def system_exe(name):
    return str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32" / name)


def python_exe(gui=False):
    name = "pythonw.exe" if gui else "python.exe"
    return str(Path(sys.executable).with_name(name)) if os.name == "nt" else sys.executable


def run_native(args, timeout=15):
    require_windows()
    return subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                          timeout=timeout, **hidden_options())


def current_sid():
    result = run_native([system_exe("whoami.exe"), "/user", "/fo", "csv", "/nh"])
    identifiers = set(re.findall(rb"S-1-\d+(?:-\d+)+", result.stdout))
    if result.returncode or len(identifiers) != 1:
        raise RuntimeError("无法确认当前用户 SID，停止操作。")
    sid = identifiers.pop().decode("ascii")
    if sid in {"S-1-5-18", "S-1-5-19", "S-1-5-20"}:
        raise RuntimeError("请用本人 Windows 桌面账号运行，不使用系统服务账号。")
    return sid


def decode_output(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if b"\x00" in data[:80]:
        return data.decode("utf-16-le")
    return data.decode("utf-8-sig")


def interrupt_times():
    """Return uptime including sleep and active uptime, in seconds."""
    require_windows()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetTickCount64.restype = ctypes.c_ulonglong
    query = kernel.QueryUnbiasedInterruptTime
    query.argtypes = [ctypes.POINTER(ctypes.c_ulonglong)]
    query.restype = ctypes.c_int
    active = ctypes.c_ulonglong()
    before = kernel.GetTickCount64() / 1000
    if not query(ctypes.byref(active)):
        raise OSError("无法读取 Windows 无偏中断时间。")
    after = kernel.GetTickCount64() / 1000
    return (before + after) / 2, active.value / 10_000_000


def print_status(value):
    if sys.stdout is not None:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(value, flush=True)
