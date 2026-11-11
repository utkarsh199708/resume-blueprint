"""A fake Anthropic API: answers /v1/messages with a canned, streamed blueprint."""

from __future__ import annotations

import json

import anthropic
import httpx2

CANNED = {
    "role": {"title": "Senior Backend Engineer", "seniority": "Senior",
             "role_family": "Backend engineering", "years_required": "5+ years",
             "domains": ["Payments"], "work_mode": "Remote",
             "one_line": "Build and run the payment services."},
    "skills": [
        {"name": "Go", "category": "Languages", "tier": "must",
         "evidence": "Strong proficiency in Go (Golang) in production",
         "jd_terms": ["Go", "Golang"]},
        # Not in the posting at all: must be dropped.
        {"name": "Rust", "category": "Languages", "tier": "must",
         "evidence": "Deep Rust expertise", "jd_terms": ["Rust"]},
        # Quote differs only in spacing and the trailing full stop: must be kept.
        {"name": "Kafka", "category": "Messaging", "tier": "must",
         "evidence": "Experience with  Kafka or another message queue.", "jd_terms": ["Kafka"]},
    ],
    "signals": [
        {"signal": "Ownership",
         "evidence": "Own features end to end, from design doc to production rollout and on-call",
         "how_to_show": "Show a launch you owned."},
        {"signal": "Invented", "evidence": "This line is not in the posting", "how_to_show": "x"},
    ],
    "resume": {
        "headline": "Senior Backend Engineer | Go · Kafka",
        "summary": "Backend engineer with [N]+ years.",
        "bullets": [{"text": "Built payment services in Go, cutting p95 latency by [X]%",
                     "proves": ["Go"],
                     "answers": "Design, build and maintain payment services in Go"}],
        "projects": [{"title": "Ledger", "description": "A double-entry ledger.",
                      "proves": ["Go"]}],
        "certifications": [], "section_order": ["Summary", "Skills", "Experience"]},
    "feedback": {"tailored_bullets": [], "actions": []},
}


def sse(payload: dict, stop_reason: str = "end_turn") -> bytes:
    text = json.dumps(payload)
    events = [
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0,
                                 "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                 "delta": {"type": "text_delta", "text": text[:50]}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                 "delta": {"type": "text_delta", "text": text[50:]}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta",
                           "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                           "usage": {"output_tokens": 500}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in events).encode()


class Recorder:
    """Records each request and answers it with the canned blueprint (or an error)."""

    def __init__(self, payload=None, stop_reason="end_turn", status=200):
        self.requests: list[httpx2.Request] = []
        self.payload = payload or CANNED
        self.stop_reason = stop_reason
        self.status = status

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx2.Response(self.status, json={"type": "error", "error": {
                "type": "authentication_error", "message": "bad key"}})
        return httpx2.Response(200, content=sse(self.payload, self.stop_reason),
                               headers={"content-type": "text/event-stream"})


def fake_client(recorder: Recorder) -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key="test-key", max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(recorder)))
