"""The shape of a blueprint. Both engines (offline rules and Claude) produce exactly this."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal["must", "nice", "implied"]


class RoleSnapshot(BaseModel):
    title: str = Field(description="The job title, as the posting states it")
    seniority: str = Field(description="Intern, Junior, Mid-level, Senior, Staff/Principal, Lead, "
                                       "or Manager")
    role_family: str = Field(description="e.g. Backend engineering, Data analytics, Product "
                                         "management")
    years_required: str = Field(description="e.g. '5+ years', or '' when the posting gives none")
    domains: list[str] = Field(description="Industry or problem domains the posting signals, "
                                           "e.g. Payments, Healthcare")
    work_mode: str = Field(description="Remote, Hybrid, On-site, or '' when not stated")
    one_line: str = Field(description="One plain sentence: what this person will actually do")


class Skill(BaseModel):
    name: str = Field(description="Canonical skill name, e.g. 'Kubernetes'")
    category: str = Field(description="e.g. Languages, Cloud & infrastructure, Soft skills")
    tier: Tier = Field(description="must = required; nice = preferred/bonus; implied = not listed "
                                   "as a requirement but the duties clearly need it")
    evidence: str = Field(description="A verbatim quote from the job description that shows "
                                      "this skill is wanted")
    jd_terms: list[str] = Field(description="The exact spellings the posting uses for it, "
                                            "e.g. ['k8s', 'Kubernetes']")
    mentions: int = Field(description="How many times the posting mentions it")


class Keyword(BaseModel):
    term: str
    count: int
    tier: Tier


class Signal(BaseModel):
    signal: str = Field(description="What the employer is really screening for, e.g. "
                                    "'End-to-end ownership'")
    evidence: str = Field(description="Verbatim quote from the posting that reveals it")
    how_to_show: str = Field(description="How to prove it on a resume")


class Bullet(BaseModel):
    text: str = Field(description="A resume bullet: past-tense action verb, what, how (tools), "
                                  "and a measurable result with concrete, realistic example "
                                  "figures (no [placeholders])")
    proves: list[str] = Field(description="Skill names this bullet proves")
    answers: str = Field(description="The duty or requirement from the posting it answers")


class Project(BaseModel):
    title: str
    description: str
    proves: list[str]


class SkillGroup(BaseModel):
    category: str
    items: list[str]


class IdealResume(BaseModel):
    headline: str = Field(description="One line under the name: target title plus 2-4 core "
                                      "skills")
    summary: str = Field(description="2-3 sentence professional summary: the title, years of "
                                     "experience as a number, and one quantified win")
    skills_section: list[SkillGroup] = Field(default_factory=list)
    bullets: list[Bullet]
    projects: list[Project]
    certifications: list[str] = Field(description="Certifications or education the posting "
                                                  "asks for or rewards")
    section_order: list[str] = Field(description="Recommended order of resume sections")


class WeakLine(BaseModel):
    line: str
    issue: str
    fix: str


class TailoredBullet(BaseModel):
    original: str
    rewritten: str


class AtsItem(BaseModel):
    """One thing an applicant tracking system screens for, and whether the resume has it."""
    label: str
    kind: Literal["must", "nice", "implied", "keyword", "title", "years", "education", "section"]
    points: float
    passed: bool
    fix: str = ""


class AtsReport(BaseModel):
    score: int
    items: list[AtsItem]

    @property
    def failed(self) -> list[AtsItem]:
        return [i for i in self.items if not i.passed]


class Fix(BaseModel):
    """A line to add to a resume, and the ATS checks it passes."""
    where: str
    text: str
    covers: list[str]


class ResumeCheck(BaseModel):
    score: int = 0
    ats: list[AtsItem] = Field(default_factory=list)
    to_100: list[Fix] = Field(default_factory=list)
    projected_score: int = 0
    matched: list[str] = Field(default_factory=list)
    missing_must: list[str] = Field(default_factory=list)
    missing_nice: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    weak_lines: list[WeakLine] = Field(default_factory=list)
    tailored_bullets: list[TailoredBullet] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class Blueprint(BaseModel):
    engine: str
    model: str = ""
    role: RoleSnapshot
    skills: list[Skill]
    keywords: list[Keyword] = Field(default_factory=list)
    signals: list[Signal]
    resume: IdealResume
    ats: AtsReport | None = None
    resume_text: str = ""
    resume_check: ResumeCheck | None = None
    notes: list[str] = Field(default_factory=list)

    def by_tier(self, tier: Tier) -> list[Skill]:
        return [s for s in self.skills if s.tier == tier]
