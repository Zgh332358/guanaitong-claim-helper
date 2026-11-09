"""Per-user Windows paths and a one-byte, non-blocking file lock."""
from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
from win_platform import require_windows

APP_ID = "guanaitong-auto-claim-windows"
ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "GuanaitongAutoClaim"
PROFILE = ROOT / "chrome-profile"
TARGET_URL = "https://c.guanaitong.com/overtime?scene_type=1"


class ProfileBusy(RuntimeError):
    pass


def require_runtime():
    require_windows()
    try:
        marker = json.loads((ROOT / "install-info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RuntimeError("请先运行 install.cmd 安装当前用户的运行环境。") from None
    if not isinstance(marker, dict) or marker.get("app_id") != APP_ID or marker.get("state") != "ready":
        raise RuntimeError("运行目录标识不符，请停止并检查，避免覆盖其他资料。")


def atomic_json(path, data):
    os.umask(0o077)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


@contextmanager
def profile_lock():
    require_runtime()
    import msvcrt
    with (ROOT / "profile.lock").open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise ProfileBusy("专用浏览器正在登录或领取，请等待该操作结束。") from None
            raise
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
