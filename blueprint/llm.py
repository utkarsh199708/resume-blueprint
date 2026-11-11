"""The Claude engine: a richer blueprint, checked against the posting before it is shown.

Claude reads the posting (and the resume, when given) and returns a structured blueprint. Before
anything reaches the page, every quote it cites is checked against the posting: a skill whose
quote is not in the posting is re-anchored to a line that names it, or dropped. Skills the rules
engine found that Claude missed are added back, so the Claude result never knows less than the
offline one.
"""

from __future__ import annotations

import os
import re

from pydantic import BaseModel, Field

from . import offline
from . import parse as P
from .models import Bullet, IdealResume, Project, RoleSnapshot, Signal, Skill, Tier
from .models import TailoredBullet as Tailored
from .taxonomy import canonical
from .writing import has_number, impact_for

DEFAULT_MODEL = "claude-opus-5-5"
PROMPT_VERSION = "2026-11-09"


class LLMSkill(BaseModel):
    name: str
    category: str
    tier: Tier
    evidence: str = Field(description="Copied character for character from the posting")
    jd_terms: list[str]


class LLMResume(BaseModel):
    headline: str
    summary: str
    bullets: list[Bullet]
    projects: list[Project]
    certifications: list[str]
    section_order: list[str]


class LLMFeedback(BaseModel):
    tailored_bullets: list[Tailored] = Field(
        description="The candidate's own weakest lines, rewritten. Empty when no resume is given")
    actions: list[str] = Field(
        description="The 5-7 highest-value edits to the candidate's resume, most important "
                    "first. Empty when no resume is given")


class LLMBlueprint(BaseModel):
    role: RoleSnapshot
    skills: list[LLMSkill]
    signals: list[Signal]
    resume: LLMResume
    feedback: LLMFeedback


SYSTEM = """\
You are a senior technical recruiter and hiring manager. A job seeker gives you a job posting, \
and sometimes their resume. You tell them exactly what the employer needs to see on a resume to \
get an interview for this job, as a structured blueprint.

How to read the posting
- skills: every skill, tool, practice, credential and trait the employer is screening for. \
tier "must" means stated as required or clearly essential; "nice" means preferred, a plus, \
bonus, ideally, familiarity; "implied" means not listed as a requirement but the duties clearly \
need it. Use the posting's own wording in jd_terms, exactly as written. Use concise canonical \
names (for example "Kubernetes", "SQL", "Stakeholder management"). Order: must, then nice, then \
implied; within a tier, most important first.
- evidence (on skills and signals): copy one sentence or bullet from the posting character for \
character. Do not paraphrase, shorten with ellipses, or fix typos. Quotes are checked \
mechanically and a quote that is not in the posting is discarded.
- signals: 4-8 things the employer is screening for that a keyword list misses (ownership, pace, \
scale, regulated environments, customer focus, ambiguity). Each with how to prove it on a resume.
- role.one_line: one plain sentence, what this person will actually spend their time doing.

How to write the ideal resume
- headline: target title plus the 3-4 skills this employer cares about most.
- summary: 2-3 sentences in the voice of an ideal candidate, using the posting's language: the \
posting's job title, years of experience as a number ("6+ years of experience", at least what \
the posting asks for), and one quantified win.
- bullets: 8-12 experience bullets the ideal candidate would have, each answering one duty or \
requirement (say which in "answers"). Past-tense action verb, what was done, with which tools, \
and a measurable result with concrete, realistic figures typical for this role and level, for \
example "cutting p95 latency by 41% at 18K requests/sec" or "informing pricing decisions worth \
$2.4M a year". Every bullet has at least one number. Vary the metrics across bullets. No \
[placeholders] or brackets: the page highlights the figures as examples for the candidate to \
replace with their own. Never name employers or products.
- projects: 2-3 portfolio projects that would prove the must-haves a candidate is most likely \
to be missing, specific to this posting.
- certifications: only those the posting asks for or would clearly reward; include degree \
requirements as stated.
- section_order: the order of resume sections that suits this role and level.

When a resume is given (feedback)
- tailored_bullets: up to 6 of the candidate's weakest relevant lines, rewritten toward this \
posting. Use only facts that are in the resume. Keep the candidate's numbers; where a result is \
missing, add a realistic example figure (the page flags it for the candidate to confirm). Never \
add a skill the resume does not show.
- actions: the 5-7 edits that would most raise this resume's chances for this posting, \
concrete and specific, most important first. Point out must-haves the resume does not show, \
without suggesting the candidate claim them.
When no resume is given, feedback has two empty lists.

Write plainly. No hype words ("rockstar", "ninja", "passionate"). British or American spelling \
as the posting uses."""


class ClaudeUnavailable(RuntimeError):
    """Claude could not be used for this request; the message says why, for the page."""


def configured_model() -> str:
    return os.environ.get("BLUEPRINT_MODEL", "").strip() or DEFAULT_MODEL


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _client():
    import anthropic

    return anthropic.Anthropic(max_retries=2, timeout=300.0)


def call_claude(jd_text: str, resume_text: str | None, client=None) -> tuple[LLMBlueprint, str]:
    import anthropic

    client = client or _client()
    model = configured_model()
    user = f"<job_posting>\n{jd_text.strip()}\n</job_posting>"
    if resume_text:
        user += f"\n\n<resume>\n{resume_text.strip()}\n</resume>"
    user += "\n\nWrite the resume blueprint for this posting."
    try:
        with client.beta.messages.stream(
            model=model,
            max_tokens=32000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": os.environ.get("BLUEPRINT_EFFORT", "medium")},
            output_format=LLMBlueprint,
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = stream.get_final_message()
    except anthropic.AuthenticationError as exc:
        raise ClaudeUnavailable("The Anthropic API key was rejected.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise ClaudeUnavailable("This API key is not allowed to use the model "
                                f"{model}.") from exc
    except anthropic.NotFoundError as exc:
        raise ClaudeUnavailable(f"The model {model} was not found.") from exc
    except anthropic.RateLimitError as exc:
        raise ClaudeUnavailable("Claude is rate-limited right now; try again shortly.") from exc
    except anthropic.APIStatusError as exc:
        raise ClaudeUnavailable(f"Claude returned an error ({exc.status_code}).") from exc
    except anthropic.APIConnectionError as exc:
        raise ClaudeUnavailable("Could not reach the Anthropic API.") from exc

    if message.stop_reason == "refusal":
        raise ClaudeUnavailable("Claude declined this request.")
    if message.stop_reason == "max_tokens":
        raise ClaudeUnavailable("Claude's answer was cut off; try a shorter posting.")
    parsed = getattr(message, "parsed_output", None)
    if parsed is None:
        raise ClaudeUnavailable("Claude's answer could not be read as a blueprint.")
    return parsed, getattr(message, "model", model) or model


# --- Checking Claude's answer against the posting --------------------------------------------

PLACEHOLDER = re.compile(r"\[[^\]]{1,60}\]")


def _numbered(text: str) -> str:
    """A sentence with a leftover [placeholder] is cut, so no bracket reaches the page."""
    if not PLACEHOLDER.search(text):
        return text
    kept = [s for s in re.split(r"(?<=[.!?])\s+", text) if not PLACEHOLDER.search(s)]
    return " ".join(kept) or PLACEHOLDER.sub("", text).strip()


def _with_numbers(bullets: list[Bullet]) -> list[Bullet]:
    """Every bullet ends in a measured result: a clause with a leftover placeholder is replaced
    by one with example figures, and a bullet with no number gets one."""
    used: set[str] = set()
    out = []
    for b in bullets:
        text = b.text.strip().rstrip(".")
        m = PLACEHOLDER.search(text)
        if m:
            cut = text.rfind(", ", 0, m.start())
            text = text[:cut] if cut > 0 else PLACEHOLDER.sub("", text).strip(" ,")
        if not has_number(text):
            text = f"{text}, {impact_for(b.answers or text, used)}"
        out.append(Bullet(text=text, proves=b.proves, answers=b.answers))
    return out

def _norm(s: str) -> str:
    s = P.normalise(s).lower()
    s = re.sub(r"^[\s\-*•·▪◦‣–—►●○]+", "", s)
    return re.sub(r"\s+", " ", s).strip(" .;,")


def _anchor(evidence: str, names: list[str], lines: list[P.Line], jd_norm: str) -> str | None:
    """The quote when it is in the posting, else a posting line naming the skill, else None."""
    if evidence and _norm(evidence) and _norm(evidence) in jd_norm:
        return evidence.strip()
    for ln in lines:
        low = ln.text.lower()
        for n in names:
            if n and len(n) > 1 and re.search(rf"(?<![a-z0-9]){re.escape(n.lower())}(?![a-z0-9])",
                                              low):
                return ln.text
    return None


def verify(raw: LLMBlueprint, jd_text: str, model: str, resume_text: str | None):
    from .models import Blueprint, ResumeCheck
    from .resume_check import check

    lines = P.split_lines(jd_text)
    jd_norm = _norm("\n".join(ln.text for ln in lines))
    jd_low = P.normalise(jd_text).lower()
    notes: list[str] = []

    skills: list[Skill] = []
    dropped = 0
    seen: set[str] = set()
    for s in raw.skills:
        key = canonical(s.name).lower()
        if key in seen:
            continue
        terms = [t for t in dict.fromkeys(s.jd_terms) if t and t.lower() in jd_low]
        ev = _anchor(s.evidence, [s.name, *terms], lines, jd_norm)
        if ev is None:
            dropped += 1
            continue
        seen.add(key)
        mentions = sum(1 for ln in lines if any(t.lower() in ln.text.lower()
                                                for t in (terms or [s.name])))
        skills.append(Skill(name=s.name, category=s.category, tier=s.tier, evidence=ev,
                            jd_terms=terms, mentions=max(mentions, 1)))
    rules = offline.extract_skills(lines)
    added = 0
    for s in rules:
        if canonical(s.name).lower() not in seen and s.tier != "implied":
            skills.append(s)
            seen.add(canonical(s.name).lower())
            added += 1
    order = {"must": 0, "nice": 1, "implied": 2}
    skills.sort(key=lambda s: order[s.tier])
    if dropped:
        notes.append(f"{dropped} skill(s) Claude cited were dropped: their quote is not in the "
                     "posting.")
    if added:
        notes.append(f"{added} skill(s) found by the rules engine were added to Claude's list.")

    signals = []
    for sig in raw.signals:
        ev = _anchor(sig.evidence, [], lines, jd_norm)
        if ev:
            signals.append(Signal(signal=sig.signal, evidence=ev, how_to_show=sig.how_to_show))

    r = raw.resume
    resume = IdealResume(headline=r.headline, summary=_numbered(r.summary),
                         skills_section=offline.skills_section_for(skills),
                         bullets=_with_numbers(r.bullets), projects=r.projects,
                         certifications=r.certifications, section_order=r.section_order)
    notes.append(offline.NUMBERS_NOTE)
    bp = Blueprint(engine="claude", model=model, role=raw.role, skills=skills,
                   keywords=offline.keywords(lines, skills, raw.role.title), signals=signals,
                   resume=resume, notes=notes)
    from .ats import complete

    complete(bp)
    if resume_text:
        rc: ResumeCheck = check(bp, resume_text)
        fb = raw.feedback
        resume_low = resume_text.lower()
        grounded = [t for t in fb.tailored_bullets
                    if t.original and _norm(t.original)[:40] in _norm(resume_low)]
        if grounded:
            rc.tailored_bullets = grounded
        if fb.actions:
            rc.actions = fb.actions[:7]
        bp.resume_check = rc
    return bp
