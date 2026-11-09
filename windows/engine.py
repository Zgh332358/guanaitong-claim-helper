"""UI-only claiming; never call private APIs or bypass eligibility checks."""
from dataclasses import dataclass, asdict
import re
import time
from urllib.parse import urlsplit
from playwright.sync_api import Error, TimeoutError

TODAY = re.compile(r"今天\s*20:30")
LOGIN_TEXT = re.compile(r"手机号登录|账号登录|工号登录|请先登[录陆]|登[录陆](?:状态|会话)?(?:已)?(?:过期|失效)|重新登[录陆]")
VERIFY_TEXT = re.compile(r"人机验证|滑动验证|请完成验证|安全验证")
LOCATION_PERMISSION_TEXT = re.compile(r"请(?:开启|打开|允许).{0,8}定位权限|定位权限.{0,8}(?:未开启|被拒绝|关闭)")
LOCATION_FAILURE_TEXT = re.compile(r"定位失败|获取(?:位置|定位)失败|无法获取(?:位置|定位)")
READY = {"领取", "立即领取", "点击领取"}
SUCCESS = {"已领取", "已领", "领取成功", "今日已领取", "已领取成功"}
CLAIMED_STAMP_PATH = "/bfe-frontend-overtime/fc5aa3deed50398c2b80.png"


@dataclass
class Outcome:
    status: str
    clicks: int = 0
    verified: bool = False
    phase: str | None = None
    error: str | None = None

    def json(self):
        return asdict(self)


def location_feedback(text):
    if LOCATION_PERMISSION_TEXT.search(text):
        return "location_permission_required"
    if LOCATION_FAILURE_TEXT.search(text):
        return "location_unavailable"
    return None


def error_kind(error):
    text = str(error).lower()
    for marker, kind in (("intercepts pointer events", "pointer_intercepted"),
                         ("detached", "element_detached"),
                         ("has been closed", "browser_closed"),
                         ("execution context", "navigation_context_changed")):
        if marker in text:
            return kind
    return "timeout" if isinstance(error, TimeoutError) else "playwright_error"


def inspect_page(page):
    url = urlsplit(page.url)
    body = page.locator("body").inner_text(timeout=3_000)
    if (url.hostname == "m.igeidao.com" and url.path.startswith("/passport")) or (
        url.hostname == "passport.guanaitong.com"
    ) or LOGIN_TEXT.search(body):
        return "login_required", None
    location_status = location_feedback(body)
    if location_status:
        return location_status, None
    if VERIFY_TEXT.search(body):
        return "manual_verification_required", None
    if url.hostname != "c.guanaitong.com" or url.path.rstrip("/") != "/overtime":
        return "unexpected_page", None
    dates = page.locator(".allowance-date").filter(has_text=TODAY)
    cards = page.locator(".meal-item-cont").filter(has=dates)
    if cards.count() != 1:
        return "card_missing_or_ambiguous", None
    button = cards.locator(".meal-operate .allowance-btn")
    if button.count() == 0:
        # The live site replaces the button with a sibling image, not text.
        row = cards.locator("..")
        if row.locator(".meal-item-cont").count() == 1:
            stamp = row.locator("img.allowance-seal")
            if stamp.count() == 1 and stamp.is_visible():
                src = urlsplit(stamp.evaluate("e => e.currentSrc || e.src"))
                if src.hostname == "static.guanaitong.com" and src.path == CLAIMED_STAMP_PATH:
                    return "already_claimed", None
    if button.count() != 1 or not button.is_visible():
        return "button_missing_or_ambiguous", None
    text = re.sub(r"\s+", "", button.inner_text())
    if text in SUCCESS:
        return "already_claimed", button
    if text == "尚未开始":
        return "not_started", button
    if text not in READY:
        return "button_unavailable", button
    classes = set((button.get_attribute("class") or "").split())
    if (button.get_attribute("disabled") is not None
            or button.get_attribute("aria-disabled") == "true"
            or classes & {"disabled", "disabled-btn", "waiting-btn"}):
        return "button_unavailable", button
    return "ready", button


def run_claim(page, *, check=False, guard=lambda: None, interval_ms=2_000,
              start_wait_seconds=0):
    """Five clicks at most, always re-read state and safety guard before clicking."""
    clicks = 0
    deadline = time.monotonic() + start_wait_seconds
    while clicks < 5:
        reason = guard()
        if reason:
            return Outcome(reason, clicks)
        status, button = inspect_page(page)
        if status == "already_claimed":
            return Outcome(status, clicks, True)
        if status == "not_started" and not check and time.monotonic() < deadline:
            page.wait_for_timeout(2_000)
            if guard():
                return Outcome("schedule_interrupted", clicks)
            page.reload(wait_until="domcontentloaded", timeout=15_000)
            page.wait_for_function("document.querySelector('.allowance-btn') || /登录/.test(document.body.innerText)", timeout=10_000)
            continue
        if status != "ready" or check:
            return Outcome(status, clicks, phase="site_feedback" if status.startswith("location_") else None)
        # Trial waits out overlays without firing a click; recheck wake/time afterwards.
        phase = "clickability_check"
        try:
            button.click(trial=True, timeout=5_000)
            reason = guard()
            if reason:
                return Outcome(reason, clicks)
            phase = "state_recheck"
            latest, button = inspect_page(page)
            if latest != "ready":
                continue
            reason = guard()
            if reason:
                return Outcome(reason, clicks)
            clicks += 1
            phase = "click"
            button.click(timeout=3_000)
            phase = "post_click_wait"
            page.wait_for_timeout(interval_ms)
        except Error as error:
            kind = error_kind(error)
            # Read the outcome before retrying: a timeout can hide a success or a site dialog.
            try:
                recovered, _ = inspect_page(page)
            except Error:
                recovered = None
            if recovered == "already_claimed":
                return Outcome(recovered, clicks, True, phase, kind)
            if recovered in {"login_required", "location_permission_required", "location_unavailable", "manual_verification_required"}:
                return Outcome(recovered, clicks, phase="site_feedback", error=kind)
            return Outcome("click_result_uncertain", clicks, phase=phase, error=kind)
    status, _ = inspect_page(page)
    if status == "already_claimed":
        return Outcome(status, clicks, True)
    return Outcome("attempts_complete" if status == "ready" else status, clicks)
