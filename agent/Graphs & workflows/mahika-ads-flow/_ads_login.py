#!/usr/bin/env python3
from __future__ import annotations
import re, subprocess, time
from pathlib import Path

SESSION = "amazon-ads"
ADS_HOME = "https://advertising.amazon.in/campaign-manager/all-campaigns?entityId=ENTITY37NJTG1VOHVTB"
AGENT_ENV = Path(__file__).resolve().parents[2] / ".env"

def load_env(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

def run(*args, timeout=120):
    cmd = ["agent-browser", "--session", SESSION, "--headed", *args]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    return ((p.stdout or "") + (p.stderr or "")).strip()

def url():
    return run("get", "url")

def snap():
    return run("snapshot", "-i")

def find_ref(snap_text, *needles):
    for line in snap_text.splitlines():
        low = line.lower()
        if all(n.lower() in low for n in needles):
            m = re.search(r"@e\d+", line)
            if m:
                return m.group(0)
    return None

SUBMIT_JS = "(()=>{const f=document.querySelector('form'); if(f){f.requestSubmit(); return 'ok'} return 'noform'})()"

def main():
    env = load_env(AGENT_ENV)
    email = env.get("AMAZON_SELLER_EMAIL", "").strip()
    password = env.get("AMAZON_SELLER_PASSWORD", "").strip()
    if not email or not password:
        print("BLOCKER: missing AMAZON_SELLER_EMAIL/PASSWORD")
        return 2
    print("open ads home...")
    run("open", ADS_HOME)
    time.sleep(4)
    u = url()
    print("url:", u[:140])
    if "advertising.amazon.in/campaign-manager" in u and "signin" not in u and "/ap/" not in u:
        print("ALREADY_LOGGED_IN")
        return 0
    s = snap()
    email_ref = find_ref(s, "textbox", "email") or find_ref(s, "textbox", "mobile")
    if email_ref:
        print("fill email...")
        run("fill", email_ref, email)
        cont = find_ref(s, "button", "Continue")
        if cont:
            run("click", cont)
        else:
            run("eval", SUBMIT_JS)
        time.sleep(4)
        print("after email:", url()[:140])
    s = snap()
    pw_ref = find_ref(s, "textbox", "Password") or find_ref(s, "password")
    if pw_ref:
        print("fill password...")
        run("fill", pw_ref, password)
        run("eval", SUBMIT_JS)
        time.sleep(6)
        print("after password:", url()[:180])
        s = snap()
        for line in s.splitlines():
            low = line.lower()
            if any(x in low for x in ["otp", "password", "sign in", "heading", "approve", "verification", "account", "campaign", "badeja", "one-time", "security"]):
                print(line)
    else:
        print("NO_PASSWORD_FIELD")
        print("\n".join(s.splitlines()[:40]))
    u = url()
    s = snap()
    if "advertising.amazon.in" in u and "signin" not in u and "/ap/" not in u:
        print("LOGIN_OK")
        return 0
    blob = (u + "\n" + s).lower()
    if "otp" in blob or "mfa" in blob or "one-time" in blob or "enter code" in blob:
        print("NEED_OTP")
        return 3
    print("LOGIN_UNKNOWN")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
