"""Bounded native Windows dialogs; only explicit user choices open manual actions."""
import argparse
import ctypes
from pathlib import Path
import subprocess
from win_platform import hidden_options, python_exe, require_windows

MESSAGES = {
    "login": ("关爱通：需要登录", "登录已失效，本次未领取。是否打开专用 Chrome 重新登录？登录完成后请手动运行一次领取。"),
    "location": ("关爱通：需要定位授权", "网站要求真实定位，本次未领取。是否打开定位授权？授权仅限关爱通站点，不会设置虚拟坐标；完成后请手动重跑。"),
    "location_error": ("关爱通：定位不可用", "未能取得真实位置。请检查 Windows 定位服务、Chrome 权限和网络，恢复后手动重跑。程序不会伪造位置。"),
    "consent": ("关爱通：真实定位授权", "是否允许后续手动领取和每日任务，仅向 c.guanaitong.com 提供浏览器真实位置？坐标不写入日志，不设置虚拟位置。授权仅保存在本机，授权后不会自动领取。"),
}


def ask(kind, timeout=60):
    require_windows()
    if kind not in MESSAGES:
        raise ValueError("Unknown dialog")
    process = subprocess.Popen([python_exe(gui=True), str(Path(__file__)), "--show", kind],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, **hidden_options())
    try:
        code = process.wait(timeout=timeout)
        return {6: "yes", 7: "no", 1: "ok"}.get(code, "error")
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)
        return "timeout"


def open_manual(script_name):
    if script_name not in {"login.py", "location_access.py"}:
        raise ValueError("Unknown manual action")
    require_windows()
    subprocess.Popen([python_exe(gui=True), str(Path(__file__).with_name(script_name))],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, **hidden_options())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", choices=MESSAGES, required=True)
    args = parser.parse_args()
    require_windows()
    title, message = MESSAGES[args.show]
    flags = 0x40 | 0x10000 | 0x40000
    if args.show != "location_error":
        flags |= 0x4 | 0x100  # Yes/No, default No; never default to consent.
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    show = user32.MessageBoxW
    show.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    show.restype = ctypes.c_int
    return show(None, message, title, flags)


if __name__ == "__main__":
    raise SystemExit(main())
