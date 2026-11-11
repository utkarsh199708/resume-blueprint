"""A blueprint as Markdown, for the CLI, the download button, and pasting into notes."""

from __future__ import annotations

from .models import Blueprint

TIER_LABEL = {"must": "Must-have", "nice": "Nice-to-have", "implied": "Implied by the duties"}


def to_markdown(bp: Blueprint) -> str:
    r = bp.role
    out: list[str] = []
    add = out.append
    add(f"# Resume blueprint: {r.title}")
    engine = "Claude" + (f" ({bp.model})" if bp.model else "") if bp.engine == "claude" \
        else "offline rules"
    add(f"_Engine: {engine}_\n")

    add("## The role at a glance")
    add(f"- **What the job is:** {r.one_line}")
    add(f"- **Level:** {r.seniority}" + (f" ({r.years_required})" if r.years_required else ""))
    add(f"- **Role family:** {r.role_family}")
    if r.domains:
        add(f"- **Domain:** {', '.join(r.domains)}")
    if r.work_mode:
        add(f"- **Work mode:** {r.work_mode}")
    add("")

    for tier in ("must", "nice", "implied"):
        items = bp.by_tier(tier)
        if not items:
            continue
        add(f"## {TIER_LABEL[tier]} ({len(items)})")
        for s in items:
            terms = [t for t in s.jd_terms if t.lower() != s.name.lower()]
            spell = f" (posting writes: {', '.join(terms[:3])})" if terms else ""
            add(f"- **{s.name}**, {s.category}{spell}. ×{s.mentions}: \"{s.evidence}\"")
        add("")

    if bp.signals:
        add("## What they are really screening for")
        for sig in bp.signals:
            add(f"- **{sig.signal}**: {sig.how_to_show}  \n  _\"{sig.evidence}\"_")
        add("")

    res = bp.resume
    add("## Your ideal resume")
    if bp.ats:
        n = len(bp.ats.items)
        passed = n - len(bp.ats.failed)
        add(f"**ATS score: {bp.ats.score}/100** (passes {passed} of {n} checks: every skill, "
            "keyword, the job title, years of experience and the standard section headings)\n")
    add(f"**Headline:** {res.headline}\n")
    add(f"**Summary:** {res.summary}\n")
    if res.skills_section:
        add("**Skills section:**")
        for g in res.skills_section:
            add(f"- {g.category}: {', '.join(g.items)}")
        add("")
    add("**Experience bullets** (the numbers are realistic examples; use your own):")
    for b in res.bullets:
        proves = f" _(proves: {', '.join(b.proves)})_" if b.proves else ""
        add(f"- {b.text}{proves}")
    add("")
    if res.projects:
        add("**Projects that would prove it:**")
        for p in res.projects:
            add(f"- **{p.title}.** {p.description}")
        add("")
    if res.certifications:
        add("**Education and certifications they mention:**")
        for c in res.certifications:
            add(f"- {c}")
        add("")
    add(f"**Section order:** {' → '.join(res.section_order)}\n")
    if bp.resume_text:
        add("**The whole resume, ready to paste** (single column, standard headings):\n")
        add("```text\n" + bp.resume_text.rstrip() + "\n```\n")

    if bp.keywords:
        add("## ATS keywords (use the posting's exact spelling)")
        add(", ".join(f"{k.term} ×{k.count}" for k in bp.keywords))
        add("")

    rc = bp.resume_check
    if rc:
        add(f"## Your resume against this posting: ATS score {rc.score}/100")
        if rc.to_100:
            add(f"\n**Add these to reach {rc.projected_score}/100** (only the ones that are "
                "true for you):")
            for f in rc.to_100:
                add(f"- _{f.where}:_ {f.text}")
            add("")
        if rc.missing_must:
            add(f"- **Missing must-haves:** {', '.join(rc.missing_must)}")
        if rc.missing_nice:
            add(f"- **Missing nice-to-haves:** {', '.join(rc.missing_nice)}")
        if rc.matched:
            add(f"- **Already there:** {', '.join(rc.matched)}")
        if rc.missing_keywords:
            add(f"- **Keywords to work in (if true):** {', '.join(rc.missing_keywords)}")
        if rc.actions:
            add("\n**Do these first:**")
            for i, a in enumerate(rc.actions, 1):
                add(f"{i}. {a}")
        if rc.tailored_bullets:
            add("\n**Lines to rewrite:**")
            for t in rc.tailored_bullets:
                add(f"- ~~{t.original}~~  \n  → {t.rewritten}")
        if rc.weak_lines:
            add("\n**Why those lines are weak:**")
            for w in rc.weak_lines:
                add(f"- \"{w.line}\": {w.issue}")
        add("")

    if bp.notes:
        add("## Notes")
        for n in bp.notes:
            add(f"- {n}")
    return "\n".join(out).rstrip() + "\n"
