"""Open only the dedicated Chrome profile for an explicit manual login."""
import re
import time
from urllib.parse import urlsplit
from playwright.sync_api import Error, TimeoutError, sync_playwright
from browser_state import restore_state, save_state
from settings import PROFILE, TARGET_URL, profile_lock


def main():
    try:
        with profile_lock(), sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(PROFILE), channel="chrome", headless=False,
                no_viewport=True, timeout=30_000,
            )
            try:
                restore_state(context)
                page = context.pages[0] if context.pages else context.new_page()
                print("请在专用 Chrome 窗口中手动登录，确认能进入领取页面。", flush=True)
                print("请暂时不要关闭窗口；识别到今日领取卡片后会保存登录状态并自动关闭。", flush=True)
                print("本程序不会领取。登录后请另外执行一次领取脚本。", flush=True)
                try:
                    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45_000)
                except TimeoutError:
                    print("页面加载较慢，可在窗口中手动刷新。", flush=True)
                deadline = time.monotonic() + 900
                saved = False
                while context.pages and time.monotonic() < deadline:
                    for current in list(context.pages):
                        try:
                            url = urlsplit(current.url)
                            if url.hostname == "m.igeidao.com" and url.path.startswith("/home"):
                                current.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30_000)
                                continue
                            if (url.hostname == "c.guanaitong.com" and url.path == "/overtime"
                                    and re.search(r"今天\s*20:30", current.locator("body").inner_text(timeout=1000))):
                                save_state(context)
                                saved = True
                                print("已识别领取页并安全保存登录状态，即将关闭专用窗口。", flush=True)
                                break
                            current.wait_for_timeout(500)
                        except Error:
                            continue
                    if saved:
                        break
                if not saved:
                    print("未保存有效的领取页登录状态，请重新登录。", flush=True)
                    return 1
            finally:
                context.close()
        print("专用 Chrome 已关闭；现在可以测试或手动运行领取脚本。", flush=True)
        return 0
    except RuntimeError as exc:
        print(str(exc), flush=True)
        return 1
    except Error:
        print("无法打开专用 Chrome；请确认已安装 Chrome 且专用窗口未被其他程序占用。", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
