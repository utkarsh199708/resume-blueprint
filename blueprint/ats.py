"""An ATS score: what an applicant tracking system screens a resume for, checked item by item.

Each check is worth points: a skill by its importance (must-have 3, nice-to-have or implied 1, a
soft skill half that), each extra keyword from the posting 0.5, the job title 4, the years of
experience asked for 2, a degree when the posting asks for one 1, and each of the four standard
section headings 1. The score is the share of points the resume earns. It is 100 only when every
check passes, never by rounding up.

The ideal resume is completed until it passes every check (``complete``), and a real resume gets
the exact lines that would take it to 100 (``path_to_100``).
"""

from __future__ import annotations

import datetime
import math
import re

from . import parse as P
from .models import AtsItem, AtsReport, Blueprint, Fix, Skill, SkillGroup
from .offline import NO_PROOF_BULLET, clean_title, proof_for, years_number
from .taxonomy import SOFT_CATEGORIES, canonical, find_matches

WEIGHT = {"must": 3.0, "nice": 1.0, "implied": 1.0}
SKILL_KINDS = ("must", "nice", "implied")
SECTIONS = {
    "Summary": r"(?:professional )?summary|profile|about me|objective",
    "Skills": r"(?:technical |key |core )?skills(?: & tools| and tools)?|technologies|tech stack|"
              r"core competencies|toolkit",
    "Experience": r"(?:professional |work |relevant )?experience|employment(?: history)?|"
                  r"work history|career history",
    "Education": r"education(?: & certifications| and certifications)?|academic background|"
                 r"qualifications",
}
CORE = "Core competencies"
RESUME_EDU = re.compile(r"\b(bachelor|master|doctorate|ph\.?\s?d|mba|degree|diploma|university|"
                        r"college|undergraduate|graduate|institute of technology)\b", re.I)


def _is_edu(text: str) -> bool:
    return bool(P.EDUCATION_WORDS.search(text) or P.EDUCATION_ABBR.search(text)
                or RESUME_EDU.search(text))


def _word(term: str, text: str, flags: int = re.I) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9+#])", text, flags))


def present(skill: Skill, text: str, canon: set[str]) -> bool:
    """Does the resume name this skill, under its name or any spelling the posting used?"""
    if canonical(skill.name) in canon:
        return True
    for term in [skill.name, *skill.jd_terms]:
        if len(term) < 2:
            continue
        exact = (term.isupper() and len(term) <= 4) or term in ("Go", "R", "C")
        if _word(term, text, 0 if exact else re.I):
            return True
    return False


def _norm(s: str) -> str:
    return re.sub(r"[\s-]+", " ", s.lower())


def years_shown(n: int, text: str) -> bool:
    """'5+ years' stated, or dates that span at least ``n`` years."""
    for m in re.finditer(r"\b(\d{1,2})\s*\+?\s*(?:years|yrs)\b", text, re.I):
        if int(m.group(1)) >= n:
            return True
    years = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-4]\d)\b", text)]
    if re.search(r"\b(present|current|now)\b", text, re.I):
        years.append(datetime.date.today().year)
    return bool(years) and max(years) - min(years) >= n


def target_title(bp: Blueprint) -> str:
    t = bp.role.title.strip()
    return "" if not t or t.lower() == "not stated" else clean_title(t)


def degree_asked(bp: Blueprint) -> str:
    return next((c for c in bp.resume.certifications
                 if P.EDUCATION_WORDS.search(c) or P.EDUCATION_ABBR.search(c)), "")


def extra_keywords(bp: Blueprint) -> list[str]:
    """Posting keywords that are not already a skill ('distributed systems', 'payment flows')."""
    taken = {_norm(t) for s in bp.skills for t in [s.name, *s.jd_terms]}
    return [k.term for k in bp.keywords if _norm(k.term) not in taken]


def ats_check(bp: Blueprint, text: str) -> AtsReport:
    canon = {m.skill.name for m in find_matches(text)}
    norm = _norm(text)
    items: list[AtsItem] = []
    have: list[str] = []
    for s in bp.skills:
        ok = present(s, text, canon)
        if ok:
            have.append(s.name)
        soft = s.category in SOFT_CATEGORIES
        items.append(AtsItem(
            label=s.name, kind=s.tier, points=WEIGHT[s.tier] * (0.5 if soft else 1.0), passed=ok,
            fix=f"Name '{s.name}' in {'a bullet or Core competencies' if soft else 'Skills'}"
                + (" and prove it in a bullet" if s.tier == "must" and not soft else "")))
    # "Python or R": either alternative meets the requirement.
    for item, s in zip(items, bp.skills, strict=True):
        ev = s.evidence
        if not item.passed and re.search(r"\bor\b|/", ev) and any(
                _word(h, ev) for h in have if h != s.name):
            item.passed = True
    for term in extra_keywords(bp):
        items.append(AtsItem(label=term, kind="keyword", points=0.5, passed=_norm(term) in norm,
                             fix=f"Work '{term}' into a bullet or Core competencies"))
    title = target_title(bp)
    if title:
        items.append(AtsItem(label=f"Job title: {title}", kind="title", points=4.0,
                             passed=_norm(title) in norm,
                             fix=f"Put '{title}' in your headline, word for word"))
    n = years_number(bp.role.years_required)
    if n:
        items.append(AtsItem(label=f"Experience: {n}+ years", kind="years", points=2.0,
                             passed=years_shown(n, text),
                             fix=f"State '{n}+ years of experience' in your summary"))
    degree = degree_asked(bp)
    if degree:
        items.append(AtsItem(label="Degree", kind="education", points=1.0, passed=_is_edu(text),
                             fix="List your degree under Education"))
    for name, pat in SECTIONS.items():
        found = re.search(rf"^\s*(?:{pat})\s*(?::.*)?$", text, re.I | re.M)
        items.append(AtsItem(label=f"Section: {name}", kind="section", points=1.0,
                             passed=bool(found),
                             fix=f"Add a heading named {name.upper()} on its own line"))
    total = sum(i.points for i in items)
    got = sum(i.points for i in items if i.passed)
    if not total:
        score = 0
    elif got == total:
        score = 100
    else:
        score = min(99, math.floor(100 * got / total))
    return AtsReport(score=score, items=items)


# --- The ideal resume, as a plain-text resume that passes every check -------------------------

def resume_text(bp: Blueprint) -> str:
    """The ideal resume as an ATS-friendly document: one column, standard headings, no tables."""
    r = bp.resume
    title = target_title(bp) or "[Your title]"
    edu = [c for c in r.certifications if _is_edu(c)]
    certs = [c for c in r.certifications if not _is_edu(c)]
    blocks = {
        "summary": ["SUMMARY", r.summary],
        "skills": ["SKILLS", *[f"{g.category}: {', '.join(g.items)}" for g in r.skills_section]],
        "experience": ["EXPERIENCE", f"{title}, [Company] | [Month Year] – Present",
                       *[f"• {b.text}" for b in r.bullets]],
        "education": ["EDUCATION", *(edu or ["[Degree], [University] | [Year]"])],
        "certifications": ["CERTIFICATIONS", *certs] if certs else [],
    }
    order: list[str] = []
    for name in r.section_order:
        key = name.split()[0].lower().rstrip(":")
        if key in blocks and key not in order:
            order.append(key)
    order += [k for k in blocks if k not in order]
    out = ["[Your Name]", "[City, Country] · [email] · [phone] · [linkedin.com/in/you]", "",
           r.headline]
    for key in order:
        if blocks[key]:
            out += ["", *blocks[key]]
    return "\n".join(out) + "\n"


def _add_skill(groups: list[SkillGroup], category: str, name: str) -> None:
    for g in groups:
        if g.category == category:
            if name not in g.items:
                g.items.append(name)
            return
    groups.append(SkillGroup(category=category, items=[name]))


def _fill_gaps(bp: Blueprint, failed: list[AtsItem]) -> None:
    r = bp.resume
    by_name = {s.name: s for s in bp.skills}
    core: list[str] = []
    for item in failed:
        if item.kind in SKILL_KINDS:
            s = by_name[item.label]
            if s.category == "Certifications":
                r.certifications.append(s.name)
            elif s.category in SOFT_CATEGORIES:
                core.append(s.name)
            else:
                _add_skill(r.skills_section, s.category, s.name)
        elif item.kind == "keyword":
            core.append(item.label[:1].upper() + item.label[1:])
        elif item.kind == "title":
            r.headline = f"{target_title(bp)} | {r.headline}"
        elif item.kind == "years":
            r.summary = (f"{r.summary.rstrip()} Brings {years_number(bp.role.years_required)}+ "
                         "years of hands-on experience.")
        elif item.kind == "education" and not any(_is_edu(c) for c in r.certifications):
            r.certifications.append(degree_asked(bp))
    for term in core:
        _add_skill(r.skills_section, CORE, term)
    # Core competencies read best last.
    r.skills_section.sort(key=lambda g: g.category == CORE)


def complete(bp: Blueprint) -> None:
    """Fill the ideal resume's gaps until it passes every ATS check; keep its text and report."""
    for _ in range(3):
        report = ats_check(bp, resume_text(bp))
        if report.score == 100:
            break
        _fill_gaps(bp, report.failed)
    bp.resume_text = resume_text(bp)
    bp.ats = ats_check(bp, bp.resume_text)


# --- A real resume: the lines that would take it to 100 ---------------------------------------

def path_to_100(bp: Blueprint, report: AtsReport, text: str) -> tuple[list[Fix], int]:
    failed = report.failed
    if not failed:
        return [], report.score
    by_name = {s.name: s for s in bp.skills}
    fixes: list[Fix] = []

    title = [i for i in failed if i.kind == "title"]
    if title:
        fixes.append(Fix(where="Headline", text=bp.resume.headline, covers=[title[0].label]))
    years = [i for i in failed if i.kind == "years"]
    if years:
        n = years_number(bp.role.years_required)
        line = next((s.strip() for s in re.split(r"(?<=\.)\s+", bp.resume.summary)
                     if years_shown(n, s)), f"{target_title(bp)} with {n}+ years of experience.")
        fixes.append(Fix(where="Summary", text=line, covers=[years[0].label]))

    hard = [i.label for i in failed if i.kind in SKILL_KINDS
            and by_name[i.label].category not in SOFT_CATEGORIES]
    if hard:
        fixes.append(Fix(where="Skills", text=", ".join(hard), covers=hard))
    used: set[str] = set()
    for name in [i.label for i in failed if i.kind == "must" and i.label in hard][:4]:
        if name in used:
            continue
        bullet = next((b for b in bp.resume.bullets if name in b.proves and _word(name, b.text)),
                      None)
        if bullet is None:
            if canonical(name) in NO_PROOF_BULLET:
                continue  # a way of working ("Stakeholder management"): the Skills line covers it
            bullet = proof_for(by_name[name])
        covers = [p for p in bullet.proves if p in hard and p not in used] or [name]
        used.update(covers)
        fixes.append(Fix(where="Experience bullet", text=bullet.text, covers=covers))

    soft = [i.label for i in failed if (i.kind in SKILL_KINDS and i.label not in hard)
            or i.kind == "keyword"]
    if soft:
        terms = [t[:1].upper() + t[1:] for t in soft]
        fixes.append(Fix(where=CORE, text=f"{CORE}: " + " · ".join(terms), covers=soft))
    degree = [i for i in failed if i.kind == "education"]
    if degree:
        fixes.append(Fix(where="Education", text=f"Your degree (they ask for: {degree_asked(bp)})",
                         covers=["Degree"]))
    for i in failed:
        if i.kind == "section":
            heading = i.label.split(": ", 1)[1].upper()
            fixes.append(Fix(where="Section heading", text=heading, covers=[i.label]))

    projected = ats_check(bp, text + "\n" + "\n".join(f.text for f in fixes)).score
    return fixes, projected
