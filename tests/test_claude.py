"""The Claude engine, against a fake Anthropic API (no key, no network)."""

import copy
import json
import re
from pathlib import Path

import pytest
from fake_claude import CANNED, Recorder, fake_client

from blueprint import engine, llm

JD = (Path(__file__).resolve().parent.parent / "samples" / "senior-backend-go.txt").read_text(
    encoding="utf-8")


def run(recorder: Recorder, resume: str | None = None):
    raw, model = llm.call_claude(JD, resume, client=fake_client(recorder))
    return llm.verify(raw, JD, model, resume)


def test_request_shape():
    rec = Recorder()
    run(rec)
    req = rec.requests[0]
    body = json.loads(req.content)
    assert req.url.path == "/v1/messages"
    assert body["model"] == "claude-opus-5-5"
    assert body["stream"] is True
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in req.headers["anthropic-beta"]
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["effort"] == "medium"
    assert "thinking" not in body and "temperature" not in body
    assert "<job_posting>" in body["messages"][0]["content"]
    assert "<resume>" not in body["messages"][0]["content"]


def test_quotes_are_checked_against_the_posting():
    bp = run(Recorder())
    names = [s.name for s in bp.skills]
    assert "Rust" not in names, "its quote is not in the posting"
    assert "Kafka" in names, "a quote differing only in spacing is accepted"
    assert [s.signal for s in bp.signals] == ["Ownership"]
    assert any("dropped" in n for n in bp.notes)


def test_claude_bullets_get_numbers_and_the_resume_scores_100():
    bp = run(Recorder())
    texts = [b.text for b in bp.resume.bullets] + [bp.resume.summary]
    assert all("[" not in t for t in texts), "leftover placeholders are replaced"
    assert all(re.search(r"\d", b.text) for b in bp.resume.bullets)
    assert bp.ats.score == 100, [i.label for i in bp.ats.failed]


def test_rules_engine_fills_what_claude_missed():
    bp = run(Recorder())
    names = {s.name for s in bp.skills}
    assert {"PostgreSQL", "Kubernetes", "Terraform"} <= names
    assert bp.engine == "claude" and bp.model == "claude-opus-5-5"
    assert bp.keywords and bp.resume.skills_section


def test_resume_feedback_must_quote_the_resume():
    payload = copy.deepcopy(CANNED)
    payload["feedback"] = {
        "tailored_bullets": [
            {"original": "Worked on the payments API", "rewritten": "Built the payments API"},
            {"original": "Invented line that is not in the resume", "rewritten": "x"},
        ],
        "actions": ["Add Kafka to your skills if you have used it."]}
    bp = run(Recorder(payload), resume="Engineer\n- Worked on the payments API in Go\n")
    rc = bp.resume_check
    assert [t.original for t in rc.tailored_bullets] == ["Worked on the payments API"]
    assert rc.actions == ["Add Kafka to your skills if you have used it."]


@pytest.mark.parametrize("recorder, message", [
    (Recorder(stop_reason="refusal"), "declined"),
    (Recorder(stop_reason="max_tokens"), "cut off"),
    (Recorder(status=401), "rejected"),
])
def test_failures_become_a_plain_reason(recorder, message):
    with pytest.raises(llm.ClaudeUnavailable, match=message):
        llm.call_claude(JD, None, client=fake_client(recorder))


def test_auto_engine_falls_back_to_offline_when_claude_fails(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm, "_client", lambda: fake_client(Recorder(status=401)))
    bp = engine.analyze(JD, engine="auto")
    assert bp.engine == "offline"
    assert "Claude was not used" in bp.notes[0]
    with pytest.raises(engine.InputError, match="rejected"):
        engine.analyze(JD, engine="claude")


def test_auto_engine_uses_claude_when_a_key_is_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm, "_client", lambda: fake_client(Recorder()))
    assert engine.analyze(JD).engine == "claude"
