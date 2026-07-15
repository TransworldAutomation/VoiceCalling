# Deploying to Oracle Cloud (Always Free, Mumbai)

This puts your voice app on a free, always-on server in India — no laptop, no tunnel,
and much lower lag. Do the phases in order. Take your time; each phase is small.

**What you'll end up with:** `https://your-name.duckdns.org` — your dashboard, always online.

---

## Phase 1 — Create the free Oracle server (~15 min)

1. Sign up at **https://www.oracle.com/cloud/free/** → "Start for free".
   - You must pick a **Home Region of Mumbai** (or Hyderabad) during signup — this can't be changed later.
   - A credit/debit card is required for identity verification. **Always Free resources are not charged.**
2. In the Oracle Console: **Menu → Compute → Instances → Create Instance**.
   - **Image:** Canonical **Ubuntu 24.04**.
   - **Shape:** click *Change Shape* → **Ampere** → **VM.Standard.A1.Flex** → set **2 OCPU, 12 GB RAM** (all Always Free eligible).
   - **SSH keys:** choose *Generate a key pair* and **download both keys** (you need the private key to log in).
   - Click **Create**. Wait until it's "Running", then copy its **Public IP address**.
3. **Open the firewall (cloud side):** Instance page → **Virtual Cloud Network** → **Security Lists** → *Default Security List* → **Add Ingress Rules**:
   - Rule 1: Source `0.0.0.0/0`, IP Protocol **TCP**, Destination port **80**
   - Rule 2: Source `0.0.0.0/0`, IP Protocol **TCP**, Destination port **443**

➡️ **Tell me your Public IP when you have it**, and we'll do Phase 2.

---

## Phase 2 — Free domain (DuckDNS) (~5 min)

Twilio needs a secure `https`/`wss` address, which needs a domain name (free).

1. Go to **https://www.duckdns.org** → sign in (Google/GitHub).
2. Pick a subdomain, e.g. `mytwvoice` → it becomes `mytwvoice.duckdns.org`.
3. In the **current ip** box, paste your server's **Public IP** → click **update ip**.

---

## Phase 3 — Get the code onto the server

Easiest is GitHub (I'll help you push it). On the server, connect via SSH first:

```bash
# from your Windows PowerShell, using the private key you downloaded:
ssh -i path\to\your-private-key ubuntu@YOUR_PUBLIC_IP
```

Then on the server:
```bash
git clone https://github.com/YOUR_USERNAME/Voice-Calling-App.git ~/Voice-Calling-App
cd ~/Voice-Calling-App
```

---

## Phase 4 — Run the installer (~5–10 min)

```bash
cd ~/Voice-Calling-App
bash deploy/setup.sh mytwvoice.duckdns.org      # <-- your DuckDNS domain
```

This installs Python 3.12, all dependencies, Caddy (auto-HTTPS), and the two services.

---

## Phase 5 — Add your keys

```bash
nano ~/Voice-Calling-App/.env
```
Paste the same keys as your local `.env`, and set:
```
PUBLIC_URL=https://mytwvoice.duckdns.org
```
Save (Ctrl+O, Enter, Ctrl+X), then:
```bash
sudo systemctl restart voice-dashboard voice-server
```

---

## Phase 6 — Use it

- Open **https://mytwvoice.duckdns.org** → your dashboard, now public.
- Type your question, pick language, Save.
- Click **Call** → your phone rings → press `1` (trial) → talk.

No laptop, no tunnel, always on, and much lower lag (server is in Mumbai).

---

### Handy server commands
```bash
sudo systemctl status voice-server        # is it running?
sudo journalctl -u voice-server -f        # live logs
tail -f ~/Voice-Calling-App/voice_server.log
sudo systemctl restart voice-server voice-dashboard
```

### Still-remaining lag
Your Twilio number is American, so audio still detours through the USA. For truly
low latency, switch to an Indian number (Exotel/Plivo) later — separate step.
