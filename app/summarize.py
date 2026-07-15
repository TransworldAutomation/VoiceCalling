"""
Ask Claude to turn a raw call transcript into a clean summary for the dashboard.

Used automatically after each real call, and you can also re-run it on any call.
"""

from app import config, database


SUMMARY_PROMPT = """You are given the transcript of a short phone interview.
Write a concise summary for a business dashboard. Use this exact markdown format:

**Outcome:** (one line — did the interview complete? was the person interested?)

**Key answers:**
- (bullet each important thing the person said)

**Sentiment:** (positive / neutral / negative, with a few words why)

**Follow-up needed:** (yes/no + what)

Keep it factual. Do not invent anything not present in the transcript.

Transcript:
---
{transcript}
---
"""


def summarize_call(call_id: int) -> str:
    """Generate and store an AI summary for one call. Returns the summary text."""
    transcript = database.get_transcript_text(call_id)
    if not transcript.strip():
        summary = "_No conversation was recorded for this call._"
        database.set_summary(call_id, summary)
        return summary

    # Imported lazily so the dashboard runs even if `anthropic` isn't installed.
    from anthropic import Anthropic

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.LLM_MODEL,
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": SUMMARY_PROMPT.format(transcript=transcript),
        }],
    )
    summary = "".join(
        block.text for block in resp.content if block.type == "text"
    ).strip()

    database.set_summary(call_id, summary)
    return summary


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python -m app.summarize <call_id>")
        raise SystemExit(1)
    print(summarize_call(int(sys.argv[1])))
