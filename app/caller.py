"""
The batch caller (Layer 2).

Reads your contacts (from the database or a CSV/Excel file) and places a real
outbound call to each one via Twilio. Twilio then connects each call to the
voice server (app/server.py), which runs the AI interview.

Usage:
    python -m app.caller                       # call everyone in the database
    python -m app.caller --file data/contacts.sample.csv
    python -m app.caller --phone +919812345678 # call a single number (great for testing)
"""

import argparse
import time

from app import config, database


def _twilio_client():
    from twilio.rest import Client
    return Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


def place_call(client, name, phone, language=None, note=None):
    """Create a call row, then tell Twilio to dial and stream to our server."""
    call_id = database.create_call(
        phone=phone, name=name, language=language or config.SARVAM_LANGUAGE, note=note
    )

    # Twilio fetches this TwiML URL when the person answers. We pass call_id as a
    # query param so the server can attach the transcript to the right record.
    twiml_url = f"{config.PUBLIC_URL}/twiml?call_id={call_id}"

    call = client.calls.create(
        to=phone,
        from_=config.TWILIO_PHONE_NUMBER,
        url=twiml_url,
        record=True,  # Twilio records the call; recording URL available afterwards
    )
    print(f"  -> Dialing {name or phone} ({phone})  call_id={call_id}  sid={call.sid}")
    return call_id


def load_from_file(path):
    import pandas as pd
    df = pd.read_excel(path) if path.lower().endswith((".xlsx", ".xls")) else pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]

    def pick(r, *names):
        for n in names:
            if n in r:
                v = str(r[n]).strip()
                if v and v.lower() != "nan":
                    return v
        return None

    people = []
    for _, r in df.iterrows():
        phone = pick(r, "phone", "number", "mobile", "contact")
        if phone:
            people.append({
                "name": pick(r, "name", "customer", "contact name"),
                "phone": phone,
                "language": pick(r, "language", "lang"),
                "note": pick(r, "notes", "note", "question", "questions"),
            })
    return people


def main():
    ap = argparse.ArgumentParser(description="Place AI interview calls.")
    ap.add_argument("--file", help="CSV/Excel of contacts to call")
    ap.add_argument("--phone", help="Call a single number (for testing)")
    ap.add_argument("--delay", type=float, default=8.0,
                    help="Seconds to wait between calls (default 8)")
    args = ap.parse_args()

    # Safety checks so a beginner gets a clear message instead of a crash.
    missing = [k for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
                           "TWILIO_PHONE_NUMBER", "PUBLIC_URL")
               if not getattr(config, k)]
    if missing:
        print("Missing settings in your .env:", ", ".join(missing))
        print("Fill them in before placing real calls (see README, Layer 2).")
        raise SystemExit(1)

    if args.phone:
        people = [{"name": None, "phone": args.phone, "language": None, "note": None}]
    elif args.file:
        people = load_from_file(args.file)
    else:
        people = [{"name": c["name"], "phone": c["phone"], "language": c["language"],
                   "note": c.get("notes")}
                  for c in database.list_contacts()]

    if not people:
        print("No one to call. Upload contacts in the dashboard or pass --file / --phone.")
        raise SystemExit(1)

    client = _twilio_client()
    print(f"Placing {len(people)} call(s)...\n")
    for i, p in enumerate(people):
        try:
            place_call(client, p["name"], p["phone"], p.get("language"), p.get("note"))
        except Exception as e:
            print(f"  x Failed to dial {p['phone']}: {e}")
        if i < len(people) - 1:
            time.sleep(args.delay)  # don't hammer the line; be polite

    print("\nDone. Watch results appear in the dashboard: http://localhost:8000")


if __name__ == "__main__":
    main()
