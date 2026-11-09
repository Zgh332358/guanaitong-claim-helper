"""Local paths and an advisory lock shared by login and claim processes."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path

ROOT = Path.home() / "Library/Application Support/GuanaitongAutoClaim"
PROFILE = ROOT / "chrome-profile"
TARGET_URL = "https://c.guanaitong.com/overtime?scene_type=1"


@contextmanager
def profile_lock(root=ROOT):
    os.umask(0o077)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "profile.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("专用浏览器正在登录或执行任务，请关闭后重试。") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
