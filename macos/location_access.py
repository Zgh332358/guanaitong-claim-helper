"""Explicit, device-local consent for real geolocation; never supplies fake coordinates."""
import argparse
from datetime import datetime
import json
import os
import subprocess
from settings import ROOT

ORIGIN = "https://c.guanaitong.com"
CONSENT = ROOT / "location-consent.json"


def location_allowed():
    try:
        data = json.loads(CONSENT.read_text(encoding="utf-8"))
        return isinstance(data, dict) and data.get("origin") == ORIGIN and data.get("allow_real_location") is True
    except (OSError, ValueError):
        return False


def set_consent(allowed):
    os.umask(0o077)
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = {"origin": ORIGIN, "allow_real_location": bool(allowed),
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    temporary = CONSENT.with_suffix(".tmp")
    temporary.write_text(json.dumps(data), encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, CONSENT)


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
    if args.revoke:
        set_consent(False)
        print("已撤销后续任务的定位授权；正在执行的任务需等待退出。")
        return 0
    dialog = '''display dialog "是否允许本工具在手动领取和每日任务运行时，仅向 c.guanaitong.com 提供浏览器的真实位置？不会设置虚拟坐标，不会把坐标写入日志或迁移包。授权仅保存在这台电脑。授权后不会自动领取，请手动运行一次领取。" with title "关爱通：真实定位授权" buttons {"取消", "允许"} default button "取消" giving up after 60'''
    try:
        result = subprocess.run(["/usr/bin/osascript", "-e", dialog], capture_output=True, text=True, timeout=65)
        if result.returncode == 0 and "button returned:允许" in result.stdout:
            set_consent(True)
            print("已授权该站点使用真实定位；未执行领取。可手动运行领取脚本。")
            return 0
        print("未变更定位授权。")
        return 0
    except (OSError, subprocess.SubprocessError):
        print("未能显示授权窗口，定位授权未变更。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
