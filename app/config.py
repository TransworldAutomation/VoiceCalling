"""
Central configuration for the AI Voice Interview Agent.

This is the main file a beginner will edit:
  - change the interview questions
  - change the language the AI speaks
  - change the AI's persona / instructions
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# API keys (read from your .env file — never hard-code secrets here)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
# PUBLIC_URL: your public https URL (no trailing slash). On Render this is set
# automatically via RENDER_EXTERNAL_URL, so you don't have to configure it.
PUBLIC_URL = os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL", "")

# Optional persistent defaults (useful on hosts with no persistent disk, like
# Render free tier, where the database resets on restart). Set these as env vars.
DEFAULT_QUESTION = os.getenv("DEFAULT_QUESTION", "")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "")

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
LLM_MODEL = "claude-sonnet-5"          # used for the after-call summary (quality)
# The live in-call brain: Haiku is much faster, which cuts conversation lag a lot.
LLM_MODEL_REALTIME = "claude-haiku-4-5-20251001"

# Sarvam voice settings. Language codes: hi-IN, mr-IN, ta-IN, te-IN, kn-IN,
# bn-IN, gu-IN, ml-IN, pa-IN, od-IN, en-IN, etc.
SARVAM_LANGUAGE = "hi-IN"              # language the AI SPEAKS the questions in
SARVAM_TTS_MODEL = "bulbul:v2"
SARVAM_TTS_VOICE = "anushka"          # a Sarvam voice id (bulbul:v2: anushka, abhilash, manisha, vidya, arya, karun, hitesh)
SARVAM_STT_MODEL = "saaras:v3"        # speech-to-text; saaras auto-detects the caller's language

# Friendly language names -> Sarvam codes, so your Excel can say "English" or "Hindi".
LANGUAGE_ALIASES = {
    "english": "en-IN", "hindi": "hi-IN", "marathi": "mr-IN", "tamil": "ta-IN",
    "telugu": "te-IN", "kannada": "kn-IN", "bengali": "bn-IN", "bangla": "bn-IN",
    "gujarati": "gu-IN", "malayalam": "ml-IN", "punjabi": "pa-IN",
    "odia": "od-IN", "oriya": "od-IN",
}


def normalize_language(value: str | None) -> str:
    """Turn 'English' / 'hindi' / 'hi-IN' into a valid Sarvam code like 'en-IN'."""
    if not value or not str(value).strip():
        return SARVAM_LANGUAGE
    v = str(value).strip()
    return LANGUAGE_ALIASES.get(v.lower(), v)


# Sarvam code -> human language name, so we can instruct Claude in plain words.
LANGUAGE_NAMES = {
    "en-IN": "English", "hi-IN": "Hindi", "mr-IN": "Marathi", "ta-IN": "Tamil",
    "te-IN": "Telugu", "kn-IN": "Kannada", "bn-IN": "Bengali", "gu-IN": "Gujarati",
    "ml-IN": "Malayalam", "pa-IN": "Punjabi", "od-IN": "Odia",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, "English")

# ---------------------------------------------------------------------------
# The interview
# ---------------------------------------------------------------------------
# The AI reads INTERVIEW_QUESTIONS in order. It will ask each one, wait for the
# answer, gently follow up if the answer is unclear, then move on. The receiver
# can reply in ANY language — the AI understands and keeps the conversation going.

INTERVIEW_QUESTIONS = [
    "What is your name and which city are you calling from?",
    "How did you hear about our company?",
    "What kind of product or service are you most interested in?",
    "What is the best time of day for us to reach you?",
    "Is there anything specific you would like our team to help you with?",
]

# The system prompt controls the AI's behaviour during the call.
#
# If the contact's row in your Excel has a 'notes' value, the AI asks ONLY that
# question (data-driven, per person). If 'notes' is empty, it falls back to the
# generic INTERVIEW_QUESTIONS list above.
def build_system_prompt(custom_question: str | None = None, language: str | None = None) -> str:
    lang = language or SARVAM_LANGUAGE
    lang_name = language_name(lang)

    # Strict, repeated language rule — otherwise the model drifts into other
    # languages when it (mis)hears the caller or the phone echo.
    language_rule = (
        f"CRITICAL LANGUAGE RULE: You MUST speak ONLY in {lang_name}. Every single "
        f"sentence you say must be in {lang_name}. Never switch to Hindi, Marathi, or "
        f"any other language, even if the caller speaks a different language or you "
        f"detect one. Always reply in {lang_name} and nothing else."
    )

    if custom_question and custom_question.strip():
        return f"""You are a warm, polite phone interviewer for a company on a live phone call.

{language_rule}

Keep every reply SHORT (1-2 sentences) and natural, like a real person on the phone.

Your ONLY task is to ask the person the exact question(s) below, one at a time, listen
to each answer, and briefly acknowledge it. Do NOT invent any other questions.

Question(s) to ask:
\"\"\"
{custom_question.strip()}
\"\"\"

Flow:
- Greet the person in one short sentence (in {lang_name}), then ask the first question.
- Ask one question at a time and wait for the answer.
- If an answer is unclear, ask one short follow-up (in {lang_name}), then continue.
- After the last question, thank them warmly and say goodbye (in {lang_name}).
"""

    questions = "\n".join(f"{i+1}. {q}" for i, q in enumerate(INTERVIEW_QUESTIONS))
    return f"""You are a warm, polite phone interviewer for a company on a live phone call.

{language_rule}

Keep every reply SHORT (1-2 sentences) and natural.

Conduct this short interview, asking ONE question at a time and waiting for the answer:

{questions}

Flow:
- Greet the person in one short sentence (in {lang_name}) and say why you are calling.
- Ask one question at a time. Do not read the whole list at once.
- If an answer is unclear, ask a brief follow-up (in {lang_name}), then move on.
- After the last question, thank them warmly and say goodbye (in {lang_name}).
"""

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DATA_DIR: where the SQLite database and recordings live. On hosts with an
# ephemeral filesystem (e.g. Render free tier) the default project folder is
# WIPED on every restart, taking your contacts and call history with it. Mount a
# persistent disk and point DATA_DIR at it (e.g. DATA_DIR=/var/data) to keep them.
DATA_DIR = os.getenv("DATA_DIR") or os.path.join(BASE_DIR, "data")
DB_PATH = os.getenv("DB_PATH") or os.path.join(DATA_DIR, "interviews.db")
RECORDINGS_DIR = os.path.join(DATA_DIR, "recordings")

# Ports
DASHBOARD_PORT = 8000
VOICE_SERVER_PORT = 8080
