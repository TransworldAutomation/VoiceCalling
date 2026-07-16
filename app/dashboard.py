"""
The web dashboard (Layer 1).

Run it with:   python -m app.dashboard
Then open:     http://localhost:8000

Shows contacts, all calls, and a detail page per call with the transcript,
AI summary, and the recording player. Also lets you upload a contact list.
"""

import io
import os

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import config, database

app = FastAPI(title="AI Voice Interview Agent")

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# We build the Jinja2 environment ourselves with cache_size=0. This disables the
# template LRU-cache, which is currently broken on Python 3.14. Rendering is fast
# enough without it for a dashboard, and it makes the app run on any Python.
_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    cache_size=0,
)


def render(template_name: str, **context) -> HTMLResponse:
    return HTMLResponse(_env.get_template(template_name).render(**context))


def _live_env() -> dict:
    """Combine the real environment (used on cloud hosts like Render) with the
    local .env file (used locally, so PUBLIC_URL written by start_calling.ps1 is
    picked up without a restart). On Render, RENDER_EXTERNAL_URL fills PUBLIC_URL."""
    from dotenv import dotenv_values
    env = dict(os.environ)
    path = os.path.join(config.BASE_DIR, ".env")
    if os.path.exists(path):
        for k, v in dotenv_values(path).items():
            if v:
                env[k] = v
    if not env.get("PUBLIC_URL") and env.get("RENDER_EXTERNAL_URL"):
        env["PUBLIC_URL"] = env["RENDER_EXTERNAL_URL"]
    return env


def _calling_status():
    """Return (env, missing_keys). If missing is empty, calling is ready."""
    env = _live_env()
    needed = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "PUBLIC_URL"]
    missing = [k for k in needed if not env.get(k)]
    return env, missing


def _not_ready_page(missing) -> HTMLResponse:
    return HTMLResponse(
        "<div style='font-family:system-ui;max-width:620px;margin:48px auto;line-height:1.6'>"
        "<h2>📞 Calling isn't switched on yet</h2>"
        f"<p>These settings are missing: <b>{', '.join(missing)}</b></p>"
        "<p>The dashboard can trigger calls, but the actual voice engine must be running first. "
        "Open PowerShell in the project folder and run:</p>"
        "<pre style='background:#eee;padding:12px;border-radius:8px'>.\\scripts\\start_calling.ps1</pre>"
        "<p>That opens the internet tunnel, sets <code>PUBLIC_URL</code>, and starts the voice server. "
        "Leave that window open, then come back here and click <b>Call</b> again.</p>"
        "<p><a href='/'>← Back to dashboard</a></p></div>",
        status_code=400,
    )


def _place_twilio_call(env, name, phone, language, note=None) -> int:
    """Create a call row and tell Twilio to dial, connecting to the voice server.

    `note` is the contact's Excel 'notes' value — the question the AI will ask.

    We SNAPSHOT the exact question + language onto this call row right now, at dial
    time. The dashboard box (the question/language you typed) is the master control
    and wins; the contact's own Excel note/language is used only as a fallback. This
    guarantees the AI asks what you just saved even if the server restarts between
    dialing and the call connecting.
    """
    global_note = (database.get_setting("interview_script") or "").strip()
    global_lang = (database.get_setting("default_language") or "").strip()

    final_note = global_note or (note.strip() if note and note.strip() else None)
    final_lang = (
        global_lang
        or (language.strip() if language and language.strip() else "")
        or config.DEFAULT_LANGUAGE
        or config.SARVAM_LANGUAGE
    )

    call_id = database.create_call(
        phone=phone, name=name, language=final_lang, note=final_note
    )
    from twilio.rest import Client
    client = Client(env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"])
    client.calls.create(
        to=phone,
        from_=env["TWILIO_PHONE_NUMBER"],
        url=f'{env["PUBLIC_URL"]}/twiml?call_id={call_id}',
        record=True,
    )
    return call_id


database.init_db()


@app.get("/", response_class=HTMLResponse)
def home():
    calls = database.list_calls()
    contacts = database.list_contacts()
    _, missing = _calling_status()
    stats = {
        "total": len(calls),
        "completed": sum(1 for c in calls if c["status"] == "completed"),
        "failed": sum(1 for c in calls if c["status"] == "failed"),
        "contacts": len(contacts),
    }
    return render(
        "index.html",
        calls=calls, contacts=contacts, stats=stats,
        calling_ready=(not missing), missing=missing,
        interview_script=database.get_setting("interview_script", "") or config.DEFAULT_QUESTION,
        default_language=database.get_setting("default_language", "")
        or config.DEFAULT_LANGUAGE or config.SARVAM_LANGUAGE,
    )


@app.post("/settings/script")
def save_script(question: str = Form(""), language: str = Form("")):
    database.set_setting("interview_script", question.strip())
    if language.strip():
        database.set_setting("default_language", language.strip())
    return RedirectResponse(url="/", status_code=303)


@app.post("/contacts/{contact_id}/call")
def call_contact(contact_id: int):
    env, missing = _calling_status()
    if missing:
        return _not_ready_page(missing)
    c = next((x for x in database.list_contacts() if x["id"] == contact_id), None)
    if not c:
        return HTMLResponse("Contact not found", status_code=404)
    try:
        _place_twilio_call(env, c["name"], c["phone"], c.get("language"), c.get("notes"))
    except Exception as e:
        return HTMLResponse(
            f"<p>Twilio couldn't place the call: {e}</p><p><a href='/'>← Back</a></p>",
            status_code=400,
        )
    return RedirectResponse("/", status_code=303)


@app.post("/call-all")
def call_all():
    env, missing = _calling_status()
    if missing:
        return _not_ready_page(missing)
    errors = []
    for c in database.list_contacts():
        try:
            _place_twilio_call(env, c["name"], c["phone"], c.get("language"), c.get("notes"))
        except Exception as e:
            errors.append(f'{c["phone"]}: {e}')
    if errors:
        items = "".join(f"<li>{x}</li>" for x in errors)
        return HTMLResponse(
            f"<p>Some calls failed:</p><ul>{items}</ul><p><a href='/'>← Back</a></p>"
        )
    return RedirectResponse("/", status_code=303)


@app.get("/call/{call_id}", response_class=HTMLResponse)
def call_detail(call_id: int):
    call = database.get_call(call_id)
    if not call:
        return HTMLResponse("Call not found", status_code=404)
    messages = database.get_messages(call_id)
    return render("call_detail.html", call=call, messages=messages)


@app.post("/upload")
async def upload_contacts(file: UploadFile = File(...)):
    """Accept a CSV or Excel file of contacts and store them."""
    import pandas as pd

    raw = await file.read()
    name = (file.filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(raw))
    else:
        df = pd.read_csv(io.BytesIO(raw))

    df.columns = [str(c).strip().lower() for c in df.columns]

    def pick(row, *names):
        for n in names:
            if n in row:
                v = str(row[n]).strip()
                if v and v.lower() != "nan":
                    return v
        return None

    added = 0
    for _, row in df.iterrows():
        phone = pick(row, "phone", "number", "mobile", "contact")
        if not phone:
            continue
        database.add_contact(
            name=pick(row, "name", "customer", "contact name"),
            phone=phone,
            language=pick(row, "language", "lang"),
            notes=pick(row, "notes", "note", "question", "questions"),
        )
        added += 1

    return RedirectResponse(url="/", status_code=303)


@app.get("/recordings/{filename}")
def get_recording(filename: str):
    """Serve a saved call recording."""
    path = os.path.join(config.RECORDINGS_DIR, os.path.basename(filename))
    if os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse("Recording not available", status_code=404)


@app.post("/call/{call_id}/resummarize")
def resummarize(call_id: int):
    from app.summarize import summarize_call
    summarize_call(call_id)
    return RedirectResponse(url=f"/call/{call_id}", status_code=303)


def main():
    import uvicorn
    print(f"\n  Dashboard running ->  http://localhost:{config.DASHBOARD_PORT}\n")
    uvicorn.run(app, host="0.0.0.0", port=config.DASHBOARD_PORT)


if __name__ == "__main__":
    main()
