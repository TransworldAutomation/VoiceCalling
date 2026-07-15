"""
Load demo data so you can SEE the dashboard working before any real calls.

Run:  python -m scripts.seed_demo
"""

from app import database

DEMO = [
    {
        "name": "Rahul Sharma", "phone": "+919812300001", "language": "hi-IN",
        "status": "completed",
        "summary": (
            "**Outcome:** Interview completed. Person is interested in a home loan.\n\n"
            "**Key answers:**\n"
            "- From Pune; heard about us via a friend.\n"
            "- Interested in home loan products.\n"
            "- Best time to call: evenings after 6 PM.\n\n"
            "**Sentiment:** Positive — friendly and engaged.\n\n"
            "**Follow-up needed:** Yes — send loan brochure and schedule an evening callback."
        ),
        "turns": [
            ("agent", "नमस्ते! मैं ट्रांसवर्ल्ड से बोल रहा हूँ। क्या मैं आपसे दो मिनट बात कर सकता हूँ?"),
            ("user", "हाँ बोलिए."),
            ("agent", "धन्यवाद! आपका नाम और आप किस शहर से हैं?"),
            ("user", "मेरा नाम राहुल शर्मा है, मैं पुणे से हूँ."),
            ("agent", "आपने हमारे बारे में कैसे सुना?"),
            ("user", "एक दोस्त ने बताया था."),
            ("agent", "आपको किस प्रोडक्ट में रुचि है?"),
            ("user", "मुझे home loan चाहिए."),
            ("agent", "आपसे संपर्क करने का सबसे अच्छा समय क्या है?"),
            ("user", "शाम को 6 बजे के बाद."),
            ("agent", "बहुत बढ़िया, धन्यवाद राहुल जी! हमारी टीम जल्द संपर्क करेगी. नमस्ते!"),
        ],
    },
    {
        "name": "Priya Nair", "phone": "+919812300002", "language": "en-IN",
        "status": "completed",
        "summary": (
            "**Outcome:** Interview completed. Curious but not ready to commit.\n\n"
            "**Key answers:**\n"
            "- From Kochi; found us on Instagram.\n"
            "- Interested in insurance, comparing options.\n"
            "- Prefers to be contacted over WhatsApp.\n\n"
            "**Sentiment:** Neutral — polite, still evaluating.\n\n"
            "**Follow-up needed:** Yes — send an insurance comparison over WhatsApp."
        ),
        "turns": [
            ("agent", "Hello! This is an assistant calling from Transworld. Do you have a moment?"),
            ("user", "Yeah, sure."),
            ("agent", "May I know your name and city?"),
            ("user", "Priya Nair, from Kochi."),
            ("agent", "How did you hear about us?"),
            ("user", "I saw you on Instagram."),
            ("agent", "Which product are you interested in?"),
            ("user", "Insurance, but I'm still comparing."),
            ("agent", "How would you like us to follow up?"),
            ("user", "WhatsApp is best."),
            ("agent", "Perfect, thank you Priya! We'll send details on WhatsApp. Have a great day!"),
        ],
    },
    {
        "name": "Amit Verma", "phone": "+919812300003", "language": "hi-IN",
        "status": "failed",
        "summary": "**Outcome:** Call not answered / disconnected early.\n\n**Follow-up needed:** Yes — retry at a different time.",
        "turns": [],
    },
]


def main():
    database.init_db()
    for d in DEMO:
        call_id = database.create_call(phone=d["phone"], name=d["name"], language=d["language"])
        for role, content in d["turns"]:
            database.add_message(call_id, role, content)
        database.finish_call(call_id, status=d["status"], summary=d["summary"])
        # also add as a contact
        database.add_contact(d["name"], d["phone"], d["language"], "demo contact")
        print(f"  seeded call #{call_id}: {d['name']} ({d['status']})")
    print("\nDemo data loaded. Start the dashboard:  python -m app.dashboard")


if __name__ == "__main__":
    main()
