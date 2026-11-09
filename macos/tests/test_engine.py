import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
from engine import run_claim
from location_access import probe_real_location
from settings import TARGET_URL

FIXTURE = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<style>body{font:18px sans-serif;background:#fff5d6;padding:40px}.meal-item-cont{display:flex;justify-content:space-between;padding:32px;background:white;margin:16px}.allowance-btn{background:#ffae20;padding:16px;cursor:pointer}.allowance-date{color:#9c6500}</style>
<div class="meal-item-cont"><div><h2>奋斗食代</h2><div class="allowance-date">今天20:30-今天23:59可领</div><p>已领 0 人</p></div>
<div class="meal-operate"><p>25.00</p><div class="allowance-btn" onclick="window.clicks++; ACTION">领取</div></div></div>
<div class="meal-item-cont"><div class="allowance-date">明天20:30-明天23:59可领</div><div class="meal-operate"><div class="allowance-btn" onclick="window.tomorrow++">领取</div></div></div>
<script>window.clicks=0;window.tomorrow=0;</script></html>"""


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = sync_playwright().start()
        cls.browser = cls.p.chromium.launch(channel="chrome", headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.p.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        # Every request is intercepted: no real claim or third-party request is possible.
        self.context.route("**/*", lambda route: route.fulfill(
            body=FIXTURE.replace("ACTION", ""), content_type="text/html"))
        self.page = self.context.new_page()
        self.page.goto(TARGET_URL)

    def tearDown(self):
        self.context.close()

    def run_claim(self, **kwargs):
        return run_claim(self.page, interval_ms=50, **kwargs)

    def test_exactly_five_when_still_available(self):
        result = self.run_claim()
        self.assertEqual((result.status, result.clicks, result.verified), ("attempts_complete", 5, False))
        self.assertEqual(self.page.evaluate("[clicks,tomorrow]"), [5, 0])

    def test_success_stops_after_one(self):
        self.page.set_content(FIXTURE.replace("ACTION", "this.innerText='已领取'"))
        result = self.run_claim()
        self.assertTrue(result.verified)
        self.assertEqual(result.clicks, 1)

    def test_check_does_not_click(self):
        self.assertEqual(self.run_claim(check=True).status, "ready")
        self.assertEqual(self.page.evaluate("clicks"), 0)

    def test_login_redirect_stops(self):
        self.page.goto("https://m.igeidao.com/passport")
        self.assertEqual(self.run_claim().status, "login_required")
        self.assertEqual(self.page.evaluate("clicks"), 0)

    def test_login_expiry_midway_stops(self):
        self.page.set_content(FIXTURE.replace("ACTION", "this.innerText='请重新登录'"))
        self.assertEqual(self.run_claim().status, "login_required")
        self.assertEqual(self.page.evaluate("clicks"), 1)

    def test_not_started_and_disabled_never_clicked(self):
        button = self.page.locator(".allowance-btn").first
        button.evaluate("e => e.innerText='尚未开始'")
        self.assertEqual(self.run_claim().status, "not_started")
        button.evaluate("e => {e.innerText='领取';e.setAttribute('aria-disabled','true')}")
        self.assertEqual(self.run_claim().status, "button_unavailable")
        self.assertEqual(self.page.evaluate("clicks"), 0)

    def test_already_claimed_does_not_use_count_as_evidence(self):
        self.page.locator(".allowance-btn").first.evaluate("e => e.innerText='已领取'")
        result = self.run_claim()
        self.assertTrue(result.verified)
        self.assertEqual(result.clicks, 0)

    def add_stamp(self, index=0, image="fc5aa3deed50398c2b80.png"):
        self.page.locator(".meal-item-cont").nth(index).evaluate("""(card, image) => {
            const wrapper = document.createElement('div');
            card.before(wrapper); wrapper.appendChild(card);
            card.querySelector('.allowance-btn').remove();
            const stamp = document.createElement('img');
            stamp.className = 'allowance-seal'; stamp.width = 60; stamp.height = 60;
            stamp.src = 'https://static.guanaitong.com/bfe-frontend-overtime/' + image;
            wrapper.appendChild(stamp);
        }""", image)

    def test_claimed_image_stamp_is_success_without_button(self):
        self.add_stamp()
        result = self.run_claim()
        self.assertEqual(result.status, "already_claimed")
        self.assertTrue(result.verified)
        self.assertEqual(result.clicks, 0)

    def test_tomorrow_stamp_does_not_mark_today_claimed(self):
        self.add_stamp(index=1)
        self.assertEqual(self.run_claim(check=True).status, "ready")

    def test_unknown_stamp_is_not_assumed_to_be_success(self):
        self.add_stamp(image="unknown-status.png")
        self.assertEqual(self.run_claim().status, "button_missing_or_ambiguous")

    def test_absent_button_alone_is_not_success(self):
        self.page.locator(".allowance-btn").first.evaluate("e => e.remove()")
        self.assertFalse(self.run_claim().verified)

    def test_duplicate_today_cards_fail_closed(self):
        self.page.locator(".allowance-date").last.evaluate("e => e.innerText='今天20:30-今天23:59可领'")
        self.assertEqual(self.run_claim().status, "card_missing_or_ambiguous")
        self.assertEqual(self.page.evaluate("clicks"), 0)

    def test_wake_between_trial_and_click_stops(self):
        reasons = iter([None, "missed_while_asleep"])
        result = self.run_claim(guard=lambda: next(reasons))
        self.assertEqual(result.status, "missed_while_asleep")
        self.assertEqual(self.page.evaluate("clicks"), 0)

    def test_midnight_after_inspection_stops_before_click(self):
        reasons = iter([None, None, "outside_schedule_window"])
        result = self.run_claim(guard=lambda: next(reasons))
        self.assertEqual(result.status, "outside_schedule_window")
        self.assertEqual(self.page.evaluate("clicks"), 0)

    def test_verification_does_not_bypass(self):
        self.page.locator(".allowance-btn").first.evaluate("e => e.innerText='请完成验证'")
        self.assertEqual(self.run_claim().status, "manual_verification_required")

    def test_location_dialog_after_click_is_reported(self):
        self.page.locator(".allowance-btn").first.evaluate("""e => e.addEventListener('click', () => {
            const overlay = document.createElement('div');
            overlay.style = 'position:fixed;inset:0;z-index:99999;background:white';
            overlay.textContent = '请开启手机定位权限 我知道了';
            document.body.appendChild(overlay);
        })""")
        result = self.run_claim()
        self.assertEqual(result.status, "location_permission_required")
        self.assertEqual(result.clicks, 1)
        self.assertEqual(self.page.evaluate("clicks"), 1)

    def test_existing_location_dialog_prevents_click(self):
        self.page.locator("body").evaluate("e => e.appendChild(Object.assign(document.createElement('div'),{textContent:'请开启手机定位权限'}))")
        result = self.run_claim()
        self.assertEqual(result.status, "location_permission_required")
        self.assertEqual(result.clicks, 0)

    def test_native_location_errors_are_classified_without_coordinates(self):
        # This browser is fully network-intercepted; only the error callback is simulated.
        for code, expected in ((1, "location_permission_required"), (2, "location_unavailable"), (3, "location_timeout")):
            self.page.evaluate("code => {navigator.geolocation.getCurrentPosition = (ok, fail) => fail({code})}", code)
            self.assertEqual(probe_real_location(self.page, timeout_ms=100), expected)

    def test_visual_fixture(self):
        path = Path(__file__).resolve().parents[1] / "artifacts" / "fixture.png"
        path.parent.mkdir(exist_ok=True)
        self.page.screenshot(path=str(path), full_page=True)
        self.assertEqual(self.run_claim(check=True).status, "ready")


if __name__ == "__main__":
    unittest.main()
