"""Hold a resume up against a blueprint: what is covered, what is missing, which lines are weak."""

from __future__ import annotations

import re

from .ats import SKILL_KINDS, ats_check, path_to_100
from .models import Blueprint, ResumeCheck, TailoredBullet, WeakLine
from .taxonomy import SOFT_CATEGORIES
from .writing import BULLET_MARK, WEAK_OPENERS, has_number, strengthen, to_past_tense


def unspace_headings(text: str) -> str:
    """PDF exports often letter-space headings: 'S K I L L S' -> 'SKILLS'."""
    def join(m: re.Match) -> str:
        return re.sub(r"(?<=\S) (?=\S)", "", m.group(0)).replace("  ", " ")
    text = re.sub(r"(?<![A-Za-z])(?:[A-Z] {1,2}){2,}[A-Z](?![A-Za-z])", join, text)
    # Unevenly spaced ones too: 'EDUC AT ION' -> 'EDUCATION'.
    out = []
    for line in text.split("\n"):
        key = re.sub(r"\s+", "", line)
        if re.fullmatch(r"[A-Z&]+", key) and key in HEADING_FORMS:
            line = HEADING_FORMS[key]
        out.append(line)
    return "\n".join(out)


HEADING_FORMS = {h.replace(" ", ""): h for h in (
    "SUMMARY", "PROFESSIONAL SUMMARY", "PROFILE", "SKILLS", "TECHNICAL SKILLS", "KEY SKILLS",
    "CORE COMPETENCIES", "EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE",
    "EMPLOYMENT HISTORY", "EDUCATION", "PROJECTS", "CERTIFICATIONS", "ACHIEVEMENTS", "AWARDS",
    "PUBLICATIONS", "LANGUAGES")}


def _candidate_lines(resume_text: str) -> list[str]:
    """Lines that read like experience bullets: listed, or led by a verb."""
    out = []
    for raw in resume_text.replace("\r", "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        listed = bool(BULLET_MARK.match(line))
        text = BULLET_MARK.sub("", line).strip()
        words = len(text.split())
        verb_led = bool(WEAK_OPENERS.match(text)) or to_past_tense(text)[1] \
            or bool(re.match(r"[A-Z][a-z]+ed\b", text))
        if text.count(",") >= 4 and not verb_led:
            continue  # a skills list, not an experience line
        if words >= 5 and (listed or verb_led):
            if re.search(r"@|https?://|linkedin|github\.com|\+?\d[\d\s-]{8,}", text, re.I):
                continue  # contact lines
            out.append(text)
    return out


def check(bp: Blueprint, resume_text: str) -> ResumeCheck:
    resume_text = unspace_headings(resume_text)
    report = ats_check(bp, resume_text)
    skill_items = [i for i in report.items if i.kind in SKILL_KINDS]
    matched = [i.label for i in skill_items if i.passed]
    missing_must = [i.label for i in skill_items if i.kind == "must" and not i.passed]
    missing_nice = [i.label for i in skill_items if i.kind == "nice" and not i.passed]
    missing_kw = [i.label for i in report.items if i.kind == "keyword" and not i.passed][:12]
    to_100, projected = path_to_100(bp, report, resume_text)
    low = resume_text.lower()

    weak: list[WeakLine] = []
    tailored: list[TailoredBullet] = []
    used: set[str] = set()  # result phrasings already suggested, so rewrites do not repeat
    lines = _candidate_lines(resume_text)
    unquantified = 0
    for line in lines:
        issues = []
        if WEAK_OPENERS.match(line):
            issues.append("starts with a passive phrase instead of an action verb")
        if not has_number(line):
            unquantified += 1
            issues.append("has no number, so the impact is invisible")
        if len(line) > 230:
            issues.append("is too long to scan; one line, two at most")
        if issues and len(weak) < 8:
            weak.append(WeakLine(line=line, issue="; ".join(issues),
                                 fix="Lead with a strong past-tense verb and end with a measured "
                                     "result."))
            rewritten = strengthen(line, used)
            if len(tailored) < 6 and rewritten.rstrip(".") != line.rstrip("."):
                tailored.append(TailoredBullet(original=line, rewritten=rewritten))

    failed = {i.kind: i for i in report.items if not i.passed and i.kind not in SKILL_KINDS}
    missing_sections = [i.label.split(": ", 1)[1] for i in report.items
                        if i.kind == "section" and not i.passed]

    actions: list[str] = []
    if missing_must:
        actions.append("Add the must-haves you genuinely have to your Skills section and to at "
                       f"least one bullet each: {', '.join(missing_must[:6])}.")
    if lines and unquantified:
        actions.append(f"{unquantified} of {len(lines)} experience lines have no number. Add a "
                       "result to each: %, $, time saved, users, or scale.")
    if "title" in failed:
        actions.append(f"Use the posting's title in your headline: \"{bp.resume.headline}\".")
    spelled = [s for s in bp.skills if s.name in matched and s.jd_terms
               and s.jd_terms[0].lower() not in low and s.category not in SOFT_CATEGORIES]
    if spelled:
        actions.append("Mirror the posting's spelling so keyword scans match: " + ", ".join(
            f"'{s.jd_terms[0]}'" for s in spelled[:4]) + ".")
    if missing_sections:
        actions.append(f"Add standard headings ATS software looks for: "
                       f"{', '.join(h.upper() for h in missing_sections)}.")
    if "years" in failed:
        actions.append(f"The posting asks for {bp.role.years_required}; say it in your summary "
                       "('6+ years of experience') so a scan finds it without date arithmetic.")
    if missing_nice:
        actions.append(f"If true, mention these nice-to-haves: {', '.join(missing_nice[:5])}.")

    return ResumeCheck(score=report.score, ats=report.items, to_100=to_100,
                       projected_score=projected, matched=matched, missing_must=missing_must,
                       missing_nice=missing_nice, missing_keywords=missing_kw,
                       weak_lines=weak, tailored_bullets=tailored, actions=actions[:7])
