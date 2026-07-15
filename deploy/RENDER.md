# Deploy to Render (free, browser-only)

No terminal on a server, no Linux commands. Three phases, all in the browser.

**Result:** a live URL like `https://voice-interview-agent.onrender.com`.

---

## Phase A — Put your code on GitHub (one-time)

Render deploys *from GitHub*, so your code needs to live there.

1. Create a free account at **https://github.com** (skip if you have one).
2. I'll help you push this folder to a new repo (we'll do it together in a few commands,
   or you can use **GitHub Desktop** — a click-only app: https://desktop.github.com).
3. Your `.env` (with secret keys) is **NOT** uploaded — it's git-ignored. Good.

---

## Phase B — Create the service on Render (~5 min)

1. Sign up at **https://render.com** with your **GitHub** account (one click).
2. Click **New +** → **Blueprint**.
3. Pick your **Voice-Calling-App** repo. Render finds `render.yaml` automatically and
   shows one service: **voice-interview-agent**. Click **Apply**.
4. Render starts building (installs Python + all dependencies — a few minutes).

---

## Phase C — Add your keys (~3 min)

While it builds (or after), open the service → **Environment** tab → add these
(same values as your local `.env`):

| Key | Value |
|-----|-------|
| `ANTHROPIC_API_KEY` | your sk-ant-... key |
| `SARVAM_API_KEY` | your Sarvam key |
| `TWILIO_ACCOUNT_SID` | AC... |
| `TWILIO_AUTH_TOKEN` | your token |
| `TWILIO_PHONE_NUMBER` | +12408965285 |
| `DEFAULT_QUESTION` | the question the AI should ask, e.g. *What is your name and city?* |
| `DEFAULT_LANGUAGE` | `en-IN` (already set) |

You do **not** set `PUBLIC_URL` — Render fills it in automatically.

Click **Save** → Render redeploys with the keys.

---

## Phase D — Use it

1. Open your Render URL: `https://<your-app>.onrender.com` → the dashboard loads.
2. Type your question, pick language, **Save**, then **📞 Call** → press `1` → talk.

---

## Honest limitations of the free tier
- **Sleeps after ~15 min idle.** Before calling, open the dashboard URL first and wait
  ~30–60s for it to wake, then place the call.
- **Memory is small (512 MB).** The AI voice models are heavy; if calls crash with
  "out of memory" in the Render **Logs**, upgrade that service to **Starter ($7/mo)**.
- **Data resets on restart** (no persistent disk on free). Your `DEFAULT_QUESTION` env var
  survives, but call history/recordings don't. Fine for testing.

## Where to look if something breaks
Render service → **Logs** tab (live). That shows the same detail as `voice_server.log`.
