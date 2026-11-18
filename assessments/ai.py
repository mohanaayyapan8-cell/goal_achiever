"""OPTIONAL AI feedback on a submitted written answer. Off unless ANTHROPIC_API_KEY is set.

PRIVACY: using it sends the question and the student's answer to the Anthropic API.
It is shown separately and NEVER changes the rubric score."""
import json
import os
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"


class AIError(Exception):
    pass


def ai_enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_ai_feedback(question, answer_text, answer_code, timeout=30):
    prompt = (
        "You are a friendly programming tutor. A beginner answered the question below. In under 150 words, say what "
        "is correct, what is missing or wrong, and give one concrete improvement. Do not just give the full solution.\n\n"
        f"QUESTION:\n{question}\n\nSTUDENT EXPLANATION:\n{answer_text or '(none)'}\n\nSTUDENT CODE:\n{answer_code or '(none)'}")
    body = json.dumps({"model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": 400,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "content-type": "application/json", "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise AIError(f"The AI service could not be reached ({exc.__class__.__name__}).") from exc
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    if not text:
        raise AIError("The AI service returned no text.")
    return text
