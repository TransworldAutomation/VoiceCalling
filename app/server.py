"""
The voice server (Layer 2).

Twilio connects to THIS server for every call:
  1. Twilio hits  POST /twiml           -> we return TwiML that opens a media stream
  2. Twilio opens WebSocket /ws         -> we run the Pipecat interview pipeline

Run it with:   python -m app.server
It must be reachable from the internet (use ngrok — see the README).
"""

import base64
import json
import os
import time
import urllib.request

from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse

from app import config, database

app = FastAPI(title="Voice Server")
database.init_db()

# Write all logs (Sarvam STT / TTS / pipeline detail) to a file we can inspect.
# At module level so it also applies inside uvicorn's auto-reload worker process.
from loguru import logger
logger.add(
    os.path.join(config.BASE_DIR, "voice_server.log"),
    level="DEBUG", rotation="5 MB", encoding="utf-8",
)


def _save_recording(call_id: int, call_sid: str):
    """After the call ends, download Twilio's recording into data/recordings/
    so it plays in the dashboard. Twilio finalizes the file a few seconds after
    the call ends, so we poll briefly."""
    from twilio.rest import Client

    client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    rec = None
    for _ in range(8):  # up to ~16s for Twilio to finalize
        recs = client.recordings.list(call_sid=call_sid, limit=1)
        if recs:
            rec = recs[0]
            break
        time.sleep(2)
    if not rec:
        print(f"No recording available yet for call {call_id}.")
        return

    os.makedirs(config.RECORDINGS_DIR, exist_ok=True)
    media_url = (
        f"https://api.twilio.com/2010-04-01/Accounts/"
        f"{config.TWILIO_ACCOUNT_SID}/Recordings/{rec.sid}.mp3"
    )
    auth = base64.b64encode(
        f"{config.TWILIO_ACCOUNT_SID}:{config.TWILIO_AUTH_TOKEN}".encode()
    ).decode()
    req = urllib.request.Request(media_url, headers={"Authorization": f"Basic {auth}"})
    fname = f"call_{call_id}.mp3"
    with urllib.request.urlopen(req, timeout=30) as r, \
            open(os.path.join(config.RECORDINGS_DIR, fname), "wb") as f:
        f.write(r.read())
    database.finish_call(call_id, status="completed", recording_url=f"/recordings/{fname}")
    print(f"Saved recording for call {call_id} -> {fname}")


@app.post("/twiml")
async def twiml(request: Request, call_id: str = ""):
    """Tell Twilio to stream the call audio to our websocket.

    The caller passes ?call_id=N so we can attach this call's transcript to the
    right database row. We forward it to the stream as a <Parameter>, which shows
    up in the websocket 'start' event as customParameters.
    """
    ws_url = config.PUBLIC_URL.replace("https://", "wss://").replace("http://", "ws://")
    param = f'<Parameter name="call_id" value="{call_id}" />' if call_id else ""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}/ws">
      {param}
    </Stream>
  </Connect>
</Response>"""
    return HTMLResponse(content=xml, media_type="application/xml")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Twilio sends a "connected" then a "start" message with the call metadata.
    # We read messages until we have the stream + call SIDs.
    stream_sid = None
    call_sid = None
    for _ in range(3):
        message = await websocket.receive_text()
        data = json.loads(message)
        if data.get("event") == "start":
            stream_sid = data["start"]["streamSid"]
            call_sid = data["start"]["callSid"]
            break

    if not stream_sid:
        await websocket.close()
        return

    # Match this stream to the call row the caller created (via custom parameter),
    # or fall back to creating one.
    call_id = None
    try:
        params = data["start"].get("customParameters", {})
        if params.get("call_id"):
            call_id = int(params["call_id"])
    except Exception:
        pass
    if call_id is None:
        call_id = database.create_call(phone="unknown")

    # Import here so the dashboard-only environment never needs Pipecat installed.
    from app.bot import run_bot
    from app.summarize import summarize_call

    try:
        await run_bot(websocket, stream_sid, call_sid, call_id)
        database.finish_call(call_id, status="completed")
    except Exception as e:
        database.finish_call(call_id, status="failed")
        print(f"Call {call_id} failed: {e}")
    finally:
        # Download the call recording (best effort).
        try:
            if call_sid:
                _save_recording(call_id, call_sid)
        except Exception as e:
            print(f"Could not save recording for call {call_id}: {e}")
        # Generate the AI summary once the call ends.
        try:
            summarize_call(call_id)
        except Exception as e:
            print(f"Could not summarize call {call_id}: {e}")


def main():
    import uvicorn
    print(f"\n  Voice server running on port {config.VOICE_SERVER_PORT}")
    print("  Logs -> voice_server.log\n")
    uvicorn.run(app, host="0.0.0.0", port=config.VOICE_SERVER_PORT)


if __name__ == "__main__":
    main()
