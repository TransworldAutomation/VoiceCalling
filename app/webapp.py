"""
Combined single-port app for cloud deployment (e.g. Render).

Locally you run the dashboard (8000) and voice server (8080) separately. A cloud
web service exposes only ONE port, so here we serve BOTH on one FastAPI app:

  - the dashboard routes  (/, /settings/script, /contacts/.../call, /recordings, ...)
  - the Twilio voice endpoints  (/twiml, /ws)

Start command (Render sets $PORT):
    uvicorn app.webapp:app --host 0.0.0.0 --port $PORT
"""

from app.dashboard import app          # dashboard FastAPI app + all its routes
from app import server                 # voice handlers: twiml(), websocket_endpoint()

# Attach the Twilio voice endpoints onto the same app.
app.add_api_route("/twiml", server.twiml, methods=["POST"])
app.add_api_websocket_route("/ws", server.websocket_endpoint)
