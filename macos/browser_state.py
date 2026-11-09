"""Preserve session cookies/storage only inside the private local runtime directory."""
import json
import os
from urllib.parse import urlsplit
from settings import ROOT

STATE = ROOT / "auth-state.json"
ALLOWED_HOSTS = {"c.guanaitong.com", "m.igeidao.com", "passport.guanaitong.com"}


def save_state(context):
    state = context.storage_state()
    state["sessionStorage"] = {}
    for page in context.pages:
        url = urlsplit(page.url)
        if url.hostname in ALLOWED_HOSTS:
            origin = f"{url.scheme}://{url.netloc}"
            state["sessionStorage"][origin] = page.evaluate(
                "() => Object.fromEntries(Object.entries(sessionStorage))"
            )
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state), encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, STATE)


def restore_state(context):
    if not STATE.is_file():
        return
    state = json.loads(STATE.read_text(encoding="utf-8"))
    context.add_cookies(state.get("cookies", []))
    payload = json.dumps({
        "local": {item["origin"]: item["localStorage"] for item in state.get("origins", [])},
        "session": state.get("sessionStorage", {}),
    })
    context.add_init_script("""(() => {
        const data = PAYLOAD;
        for (const item of data.local[location.origin] || []) {
            if (localStorage.getItem(item.name) === null) localStorage.setItem(item.name, item.value);
        }
        for (const [key, value] of Object.entries(data.session[location.origin] || {})) {
            if (sessionStorage.getItem(key) === null) sessionStorage.setItem(key, value);
        }
    })();""".replace("PAYLOAD", payload))
