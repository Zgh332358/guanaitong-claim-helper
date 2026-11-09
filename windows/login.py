"""Visible, user-driven login to the dedicated Windows Chrome profile."""
import time
from urllib.parse import urlsplit
from playwright.sync_api import Error, TimeoutError, sync_playwright
from browser_state import restore_state, save_state
from engine import TODAY
from settings import PROFILE, TARGET_URL, ProfileBusy, profile_lock, require_runtime
from win_platform import print_status


def main():
    require_runtime()
    try:
        with profile_lock(), sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(PROFILE), channel="chrome", headless=False, no_viewport=True, timeout=30_000)
            try:
                restore_state(context)
                page = context.pages[0] if context.pages else context.new_page()
                print_status("请在专用 Chrome 中人工登录。不要提前关闭，识别到今日领取页后会保存并自动关闭；此过程不领取。")
                try:
                    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45_000)
                except TimeoutError:
                    print_status("页面加载较慢，可在专用窗口中手动刷新。")
                deadline = time.monotonic() + 900
                while context.pages and time.monotonic() < deadline:
                    for current in list(context.pages):
                        try:
                            url = urlsplit(current.url)
                            if url.hostname == "m.igeidao.com" and url.path.startswith("/home"):
                                current.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30_000)
                                continue
                            if (url.hostname == "c.guanaitong.com" and url.path == "/overtime"
                                    and TODAY.search(current.locator("body").inner_text(timeout=1000))):
                                save_state(context)
                                print_status("已保存当前会话。若已过20:30，请手动运行一次领取；本程序不会自动补领。")
                                return 0
                            current.wait_for_timeout(500)
                        except Error:
                            continue
                print_status("未保存有效领取页会话，请重新登录。")
                return 1
            finally:
                context.close()
    except ProfileBusy:
        print_status("专用浏览器正在运行，请等待另一操作结束。")
        return 1
    except (Error, OSError):
        print_status("登录失败，请检查 Chrome、网络和本机运行目录。")
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print_status(str(error))
        raise SystemExit(1)
