"""Explicit, device-local consent for real geolocation; never supplies fake coordinates."""
import argparse
from datetime import datetime
import json
from settings import ROOT, atomic_json, require_runtime
from dialogs import ask
from win_platform import print_status

ORIGIN = "https://c.guanaitong.com"
CONSENT = ROOT / "location-consent.json"


def location_allowed():
    try:
        data = json.loads(CONSENT.read_text(encoding="utf-8"))
        return isinstance(data, dict) and data.get("origin") == ORIGIN and data.get("allow_real_location") is True
    except (OSError, ValueError):
        return False


def set_consent(allowed):
    data = {"origin": ORIGIN, "allow_real_location": bool(allowed),
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    atomic_json(CONSENT, data)


def configure_location(context):
    if not location_allowed():
        return False
    context.grant_permissions(["geolocation"], origin=ORIGIN)
    return True


def probe_real_location(page, timeout_ms=15_000):
    # Return status only. Coordinates never leave the browser through this probe.
    return page.evaluate("""timeout => new Promise(resolve => {
        let finished = false;
        const finish = status => { if (!finished) { finished = true; clearTimeout(timer); resolve(status); } };
        const timer = setTimeout(() => finish('location_timeout'), timeout + 1000);
        if (!navigator.geolocation) { finish('location_unavailable'); return; }
        navigator.geolocation.getCurrentPosition(
            position => finish(Number.isFinite(position.coords.latitude) && Number.isFinite(position.coords.longitude)
                ? 'ready' : 'location_unavailable'),
            error => finish(({1:'location_permission_required',2:'location_unavailable',3:'location_timeout'})[error.code]
                || 'location_unavailable'),
            {enableHighAccuracy:true,timeout,maximumAge:0}
        );
    })""", timeout_ms)


def main():
    parser = argparse.ArgumentParser(description="授权/撤销关爱通站点的真实定位，仅保存在本机")
    parser.add_argument("--revoke", action="store_true")
    args = parser.parse_args()
    require_runtime()
    if args.revoke:
        set_consent(False)
        print_status("已撤销后续任务的定位授权；正在运行的任务需等待退出。")
        return 0
    if ask("consent") == "yes":
        set_consent(True)
        print_status("已授权本站点使用真实定位；未执行领取。")
    else:
        print_status("未变更定位授权。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
