"""
Verify the API keys in your .env actually work.

Run:  python -m scripts.check_keys

It never prints your secret keys — only PASS / FAIL for each service.
"""

import base64
import json
import urllib.request
import urllib.error

from app import config


def ok(msg):   print(f"  [PASS] {msg}")
def bad(msg):  print(f"  [FAIL] {msg}")
def info(msg): print(f"  [....] {msg}")


def check_anthropic():
    print("\nAnthropic (AI brain):")
    if not config.ANTHROPIC_API_KEY:
        return bad("ANTHROPIC_API_KEY is empty in .env")
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=config.LLM_MODEL, max_tokens=5,
            messages=[{"role": "user", "content": "Say OK"}],
        )
        ok(f"key works, model '{config.LLM_MODEL}' responded")
    except Exception as e:
        bad(f"{type(e).__name__}: {e}")


def check_twilio():
    print("\nTwilio (phone line):")
    if not (config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN):
        return bad("TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN is empty in .env")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}.json"
    auth = base64.b64encode(
        f"{config.TWILIO_ACCOUNT_SID}:{config.TWILIO_AUTH_TOKEN}".encode()
    ).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            ok(f"credentials valid — account status: {data.get('status')}")
    except urllib.error.HTTPError as e:
        bad(f"HTTP {e.code} — check Account SID / Auth Token")
    except Exception as e:
        bad(f"{type(e).__name__}: {e}")

    # Phone number sanity check
    num = config.TWILIO_PHONE_NUMBER
    if not num:
        bad("TWILIO_PHONE_NUMBER is empty")
    elif not num.startswith("+") or " " in num or not num[1:].isdigit():
        bad(f"phone number '{num}' should look like +12408965285 (no spaces)")
    else:
        ok(f"phone number format looks right ({num})")


def check_sarvam():
    print("\nSarvam AI (regional voice):")
    if not config.SARVAM_API_KEY:
        return bad("SARVAM_API_KEY is empty in .env")
    # Lightweight auth check via the translate endpoint.
    body = json.dumps({
        "input": "Hello",
        "source_language_code": "en-IN",
        "target_language_code": "hi-IN",
    }).encode()
    req = urllib.request.Request(
        "https://api.sarvam.ai/translate",
        data=body,
        headers={
            "api-subscription-key": config.SARVAM_API_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            ok("key works, translate endpoint responded")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            bad(f"HTTP {e.code} — Sarvam key looks invalid/unauthorized")
        else:
            info(f"got HTTP {e.code} (key likely OK; will confirm on a real call)")
    except Exception as e:
        info(f"could not reach Sarvam ({type(e).__name__}); will confirm on a real call")


if __name__ == "__main__":
    print("Checking your API keys (secrets are never printed)...")
    check_anthropic()
    check_twilio()
    check_sarvam()
    print("\nDone.")
