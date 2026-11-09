"""Bounded worker. Invoke launcher.py for logging, reminders and timeout supervision."""
import argparse
import json
from playwright.sync_api import Error, sync_playwright
from browser_state import restore_state, save_state
from engine import LOGIN_TEXT, VERIFY_TEXT, Outcome, error_kind, inspect_page, location_feedback, run_claim
from location_access import configure_location, probe_real_location
from scheduling import ExecutionGuard
from settings import PROFILE, TARGET_URL, ProfileBusy, profile_lock, require_runtime
from win_platform import UnsupportedPlatform, print_status


def execute(args):
    window_guard = ExecutionGuard(scheduled=args.scheduled)
    if not args.check:
        reason = window_guard()
        if reason:
            return Outcome(reason)
    with profile_lock(), sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE), channel="chrome", headless=True,
            viewport={"width": 1280, "height": 900}, timeout=30_000,
            accept_downloads=False,
        )
        try:
            restore_state(context)
            location_enabled = configure_location(context) if not args.check else False
            page = context.pages[0] if context.pages else context.new_page()
            interruptions = []

            def dialog_handler(dialog):
                if LOGIN_TEXT.search(dialog.message):
                    interruptions.append("login_required")
                elif location_feedback(dialog.message):
                    interruptions.append(location_feedback(dialog.message))
                elif VERIFY_TEXT.search(dialog.message):
                    interruptions.append("manual_verification_required")
                elif dialog.type != "alert":
                    interruptions.append("dialog_requires_user")
                dialog.dismiss()

            page.on("dialog", dialog_handler)
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=35_000)
            page.wait_for_function("""() => document.body && (
                document.querySelector('.meal-item-cont') ||
                /手机号登录|账号登录|工号登录|重新登录|人机验证|安全验证/.test(document.body.innerText)
            )""", timeout=15_000)

            def guard():
                if interruptions:
                    return interruptions[0]
                return None if args.check else window_guard()

            if not args.check:
                reason = guard()
                if reason:
                    return Outcome(reason)
                status, _ = inspect_page(page)
                if status in {"ready", "not_started"}:
                    if not location_enabled:
                        return Outcome("location_permission_required", phase="location_preflight", error="not_authorized")
                    location_status = probe_real_location(page)
                    if location_status != "ready":
                        return Outcome(location_status, phase="location_preflight")

            result = run_claim(page, check=args.check, guard=guard,
                               start_wait_seconds=20 if args.scheduled else 0)
            if result.status in {"ready", "not_started", "already_claimed", "attempts_complete",
                                 "button_unavailable", "click_result_uncertain"}:
                save_state(context)
            return result
        finally:
            context.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--check", action="store_true", help="只检查登录和按钮状态，不点击")
    args = parser.parse_args()
    try:
        require_runtime()
        result = execute(args)
    except UnsupportedPlatform:
        result = Outcome("unsupported_platform")
    except ProfileBusy:
        result = Outcome("profile_busy")
    except RuntimeError:
        result = Outcome("runtime_setup_required")
    except (Error, OSError, ValueError) as error:
        result = Outcome("browser_or_network_error", phase="browser_setup_or_navigation", error=error_kind(error))
    print_status(json.dumps(result.json(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
