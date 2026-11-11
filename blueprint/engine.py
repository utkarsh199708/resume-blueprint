"""One entry point for both engines."""

from __future__ import annotations

import os
from pathlib import Path

from . import llm, offline
from .models import Blueprint
from .resume_check import check

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ("auto", "offline", "claude")


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """KEY=VALUE lines from ``.env`` into the environment, never overriding what is set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


class InputError(ValueError):
    pass


def analyze(jd_text: str, resume_text: str | None = None, engine: str = "auto") -> Blueprint:
    jd_text = (jd_text or "").strip()
    resume_text = (resume_text or "").strip() or None
    if engine not in ENGINES:
        raise InputError(f"Unknown engine '{engine}'. Use one of: {', '.join(ENGINES)}.")
    if len(jd_text.split()) < 15:
        raise InputError("Paste the full job description (at least a few sentences).")
    if len(jd_text) > 60_000:
        raise InputError("That job description is very long (over 60,000 characters). "
                         "Paste just the posting.")

    fallback_note = None
    if engine == "claude" and not llm.available():
        raise InputError("The Claude engine needs ANTHROPIC_API_KEY set (see the README).")
    if engine == "claude" or (engine == "auto" and llm.available()):
        try:
            raw, model = llm.call_claude(jd_text, resume_text)
            return llm.verify(raw, jd_text, model, resume_text)
        except llm.ClaudeUnavailable as exc:
            if engine == "claude":
                raise InputError(str(exc)) from exc
            fallback_note = f"Claude was not used ({exc}) so this is the offline result."

    bp = offline.build(jd_text)
    if resume_text:
        bp.resume_check = check(bp, resume_text)
    if fallback_note:
        bp.notes.insert(0, fallback_note)
    return bp
