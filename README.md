# AI Voice Interview Agent

Upload a list of phone numbers → the AI calls each person → asks interview questions
in a regional language → understands their spoken answers → and shows you the
**recording, full transcript, and an AI summary** in a web dashboard.

This project is built in **two layers** so you can see progress immediately:

| Layer | What it does | Needs API keys? | Python |
|-------|--------------|-----------------|--------|
| **1. Dashboard** | Web UI: contacts, calls, recordings, transcripts, summaries | No (works with demo data) | 3.12 or 3.14 |
| **2. Voice calling** | Actually phones people & runs the AI interview | Yes (Twilio + Sarvam + Anthropic) | **3.12 only** |

Start with Layer 1 to see everything working, then turn on Layer 2 when ready.

---

## Tech stack

- **Telephony (the phone call):** [Twilio](https://twilio.com) (free trial credit to learn)
- **Speech-to-Text + Text-to-Speech (Indian regional languages):** [Sarvam AI](https://sarvam.ai)
- **AI brain (interview logic + summary):** [Anthropic Claude](https://www.anthropic.com)
- **Voice orchestration:** [Pipecat](https://github.com/pipecat-ai/pipecat) (open-source)
- **Dashboard + server:** FastAPI + SQLite

---

## ⚠️ Read this first (important for beginners)

1. **Python version:** The voice libraries (Layer 2) do **not** support Python 3.14 yet.
   Install **Python 3.12** for the calling features. The dashboard (Layer 1) works on either.
2. **"Free" telephony has limits:** the *software* here is free, but *phone calls* cost money
   at scale (~₹0.5–1/min). Twilio's free trial gives you enough credit to build and demo.
3. **India legal note:** automated calling in India requires **DLT registration** (TRAI rules)
   and **consent** from the person called. For learning, only call your own / consenting numbers.

---

## Layer 1 — Run the dashboard now (5 minutes, no API keys)

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install the light dashboard dependencies
pip install -r requirements-dashboard.txt

# 3. Load some demo calls so the dashboard looks alive
python -m scripts.seed_demo

# 4. Start the dashboard
python -m app.dashboard
```

Open http://localhost:8000 in your browser. You'll see demo contacts, a call list,
and click any call to see its transcript + AI summary + (placeholder) recording.

You can also upload your own contact list from the dashboard (CSV or Excel).
See `data/contacts.sample.csv` for the required columns.

---

## Layer 2 — Turn on real calling (when you're ready)

### A. Get your keys

1. **Twilio** – sign up, buy/claim a phone number, copy your Account SID + Auth Token.
2. **Sarvam AI** – sign up at sarvam.ai, create an API key (free tier available).
3. **Anthropic** – get an API key from console.anthropic.com.

Copy `.env.example` to `.env` and fill in the values.

### B. Install the voice stack (needs Python 3.12)

```powershell
# Make a SEPARATE venv with Python 3.12
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1
pip install -r requirements-voice.txt
```

### C. Expose your local server to the internet

Twilio needs a public URL to stream call audio to your machine. Use ngrok:

```powershell
# Download from https://ngrok.com, then:
ngrok http 8080
```

Copy the `https://xxxx.ngrok-free.app` URL into your `.env` as `PUBLIC_URL`.

### D. Start the voice server, then place calls

```powershell
# Terminal 1: the voice/bot server
python -m app.server

# Terminal 2: dial everyone in your contacts database
python -m app.caller --file data/contacts.sample.csv
```

Each call runs the interview, saves the recording + transcript, and the AI summary
appears in your dashboard automatically.

---

## Project structure

```
app/
  config.py       # interview questions + language settings (EDIT THIS to change the interview)
  database.py     # SQLite storage for contacts, calls, transcripts
  dashboard.py    # the web dashboard (Layer 1)
  summarize.py    # asks Claude to summarize each transcript
  bot.py          # the Pipecat voice pipeline: STT -> Claude -> TTS (Layer 2)
  server.py       # Twilio webhook + audio websocket (Layer 2)
  caller.py       # reads your database and places the calls (Layer 2)
  templates/      # dashboard HTML
scripts/
  seed_demo.py    # loads fake demo calls so you can see the UI
data/
  contacts.sample.csv
```

## Where to customize

- **Change the interview questions / language** → `app/config.py`
- **Change how summaries look** → `app/summarize.py`
- **Change the dashboard look** → `app/templates/`
