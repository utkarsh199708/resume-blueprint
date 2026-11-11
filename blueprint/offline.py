"""The offline engine: a blueprint from rules alone, no API key, no network."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import replace

from . import parse as P
from .families import Family, detect_family
from .models import (
    Blueprint,
    Bullet,
    IdealResume,
    Keyword,
    Project,
    RoleSnapshot,
    Signal,
    Skill,
    SkillGroup,
)
from .taxonomy import (
    DOMAIN_PATTERNS,
    SOFT_CATEGORIES,
    TECH_CATEGORIES,
    canonical,
    find_matches,
)
from .writing import (
    PRONOUNS,
    as_win,
    base_verb,
    drop_nice_tail,
    figures,
    has_number,
    impact_for,
    join_names,
    make_bullet,
    shorten,
    strip_lead_in,
    to_past_tense,
)

TIER_RANK = {"must": 0, "nice": 1, "implied": 2}
OTHER = "Other tools & platforms"


def _tidy_evidence(text: str) -> str:
    return text.strip().rstrip(";,")


def display_name(name: str, category: str, terms: list[str]) -> str:
    """The posting's own spelling when it is a proper name ('Kafka', not 'Apache Kafka').

    Applicant tracking systems match the posting's words, so the resume should use them.
    """
    if category in SOFT_CATEGORIES or not terms:
        return name
    lowered = {t.lower().rstrip("s'") for t in terms}
    if name.lower().rstrip("s'") in lowered:
        return name
    top = terms[0]
    if top[:1].isupper() and not top.endswith("s") and len(top) > 1:
        return top
    return name


# --- Skills ------------------------------------------------------------------------------------

def extract_skills(lines: list[P.Line]) -> list[Skill]:
    structured = P.has_sections(lines)
    hits: dict[str, dict] = {}
    for i, ln in enumerate(lines):
        tier = P.line_tier(ln, structured)
        if tier == "ignore":
            continue
        for m in find_matches(ln.text):
            h = hits.setdefault(m.skill.name, {
                "def": m.skill, "tiers": [], "terms": Counter(), "evidence": {}, "n": set()})
            h["tiers"].append(tier)
            h["terms"][m.surface] += 1
            h["n"].add(i)
            h["evidence"].setdefault(tier, ln.text)
    for name, info in _other_tools(lines, structured, {k.lower() for k in hits}).items():
        hits[name] = info

    skills: list[Skill] = []
    for name, h in hits.items():
        tiers, mentions = h["tiers"], len(h["n"])
        if "must" in tiers:
            tier = "must"
        elif "nice" in tiers:
            tier = "nice"
        else:
            tier = "must" if mentions >= 3 else "implied"
        category = h["def"].category if h.get("def") else OTHER
        evidence = h["evidence"].get(tier) or next(iter(h["evidence"].values()))
        terms = [t for t, _ in h["terms"].most_common()]
        skills.append(Skill(
            name=display_name(name, category, terms), category=category, tier=tier,
            evidence=_tidy_evidence(evidence), jd_terms=terms, mentions=mentions))
    skills.sort(key=lambda s: (TIER_RANK[s.tier], s.category in SOFT_CATEGORIES, -s.mentions,
                               s.name.lower()))
    return skills


COMMON_CAPS = {
    "We", "You", "Our", "The", "This", "Your", "They", "And", "Or", "With", "Experience",
    "Strong", "Knowledge", "Ability", "Familiarity", "Understanding", "Proficiency", "Excellent",
    "Good", "Great", "Solid", "Deep", "Proven", "Bachelor", "Master", "Degree", "Plus", "Bonus",
    "English", "Monday", "Friday", "January", "Senior", "Junior", "Lead", "Staff", "Team",
    "Engineering", "Product", "Design", "Data", "Sales", "Marketing", "Customer", "Customers",
    "Users", "Remote", "Hybrid", "Office", "Company", "Business", "Some", "Any", "All", "One",
    "Two", "Three", "Years", "Year", "Working", "Building", "Using", "Tools", "Systems", "Services",
    "Similar", "Other", "Etc", "Eg", "Ie", "Including", "Such", "As", "Like", "Modern", "Cloud",
    "Web", "Mobile", "Backend", "Frontend", "API", "APIs", "AI", "ML", "UI", "UX", "US", "UK", "EU",
    "CEO", "CTO", "VP", "PM", "PMs", "SaaS", "B2B", "B2C", "Q1", "Q2", "Q3", "Q4", "OKR", "KPI",
    "Hands", "Expert", "Expertise", "Comfort", "Comfortable", "Fluency", "Fluent", "Advanced",
    "Must", "Nice", "Preferred", "Required", "Ideally", "Exposure", "Background", "Track",
    "Record", "Python3", "Agile", "Scrum", "Git", "GitHub", "Open", "Source",
}
TOOLISH = re.compile(r"^(?:[A-Z][a-z]+[A-Z]\w*|[A-Z][A-Za-z]*\d[\w.]*|[A-Z]{2,6}\d*|"
                     r"[A-Z][a-z]{2,}(?:\.(?:js|io|ai))?)$")


def _other_tools(lines: list[P.Line], structured: bool, known: set[str]) -> dict[str, dict]:
    """Tools the taxonomy does not know, named in lists beside ones it does.

    "Experience with Go, Temporal and ClickHouse" yields Temporal, since it sits in a list with a
    known skill and is spelled like a product name.
    """
    found: dict[str, dict] = {}
    for i, ln in enumerate(lines):
        tier = P.line_tier(ln, structured)
        if tier == "ignore" or not find_matches(ln.text):
            continue
        pos = 0
        for frag in re.split(r",|;|/|\(|\)|\bor\b|\band\b|\be\.g\.|\bsuch as\b|\blike\b|:",
                             ln.text):
            at_start = pos == 0
            pos += len(frag) + 1
            words = frag.strip(" .").split()
            if not 1 <= len(words) <= 2:
                continue
            cand = " ".join(words)
            if any(w in COMMON_CAPS or not TOOLISH.match(w) or base_verb(w) for w in words):
                continue
            # A capitalised first word is just the start of the sentence, unless it is spelled
            # like a product (CamelCase, digits, all capitals).
            if at_start and all(re.fullmatch(r"[A-Z][a-z]+", w) for w in words):
                continue
            if cand.lower() in known or find_matches(cand) or P.EDUCATION_ABBR.fullmatch(cand):
                continue  # known already, or a degree ("MS or PhD") rather than a tool
            h = found.setdefault(cand, {"def": None, "tiers": [], "terms": Counter(),
                                        "evidence": {}, "n": set()})
            h["tiers"].append(tier)
            h["terms"][cand] += 1
            h["n"].add(i)
            h["evidence"].setdefault(tier, ln.text)
    return found


# --- Keywords ----------------------------------------------------------------------------------

STOP = set("""a an the and or of to in for with on at by from as is are be will you your our we
this that these those it its into via per about across within over under using use used etc e.g
i.e who what how why when where which while also more most other others such than then they them
their there here have has had not no can could should would may might must very well just able
work working experience years year strong great good team teams role company new help make
including include includes based like ensure related relevant across all any each every both
one two three high level best day way part ability skills knowledge understanding plus bonus
nice preferred required requirements responsibilities qualifications""".split())


def keyword_term(s: Skill) -> str:
    """How to write a skill so a keyword scan finds it: the posting's spelling of a tool, the
    plain name of a soft skill ('Ownership', not 'own the')."""
    if s.category in SOFT_CATEGORIES or not s.jd_terms:
        return s.name
    return s.name if s.name.lower() in {t.lower() for t in s.jd_terms} else s.jd_terms[0]


def keywords(text_lines: list[P.Line], skills: list[Skill], title: str = "") -> list[Keyword]:
    kws = [Keyword(term=keyword_term(s), count=s.mentions, tier=s.tier) for s in skills]
    covered = {t.lower() for s in skills for t in s.jd_terms} | {s.name.lower() for s in skills}
    grams: Counter = Counter()
    first_tier: dict[str, str] = {}
    structured = P.has_sections(text_lines)
    title_l = title.lower()
    for ln in text_lines:
        tier = P.line_tier(ln, structured)
        if tier == "ignore" or ln.section == P.ABOUT:
            continue
        words = re.findall(r"[A-Za-z][A-Za-z+#.-]*[A-Za-z+#]|[A-Za-z]", ln.text)
        for n in (2, 3):
            for i in range(len(words) - n + 1):
                gram = words[i:i + n]
                if any(w.lower() in STOP or len(w) < 3 for w in gram):
                    continue
                phrase = " ".join(gram).lower()
                if any(c in phrase or phrase in c for c in covered) or phrase in title_l:
                    continue
                grams[phrase] += 1
                first_tier.setdefault(phrase, tier)
    extras = []
    for phrase, n in grams.most_common(40):
        if n < 2:
            break
        if any(phrase in e or e in phrase for e, _ in extras):
            continue
        extras.append((phrase, n))
        if len(extras) >= 8:
            break
    kws += [Keyword(term=p, count=n, tier=first_tier[p]) for p, n in extras]
    kws.sort(key=lambda k: (TIER_RANK[k.tier], -k.count))
    return kws


# --- Hidden signals ----------------------------------------------------------------------------

SIGNALS: list[tuple[str, str, str]] = [
    ("End-to-end ownership",
     r"\b(ownership|own(?:ing)? (?:the|features?|projects?|services?|outcomes)|end[\s-]to[\s-]end|"
     r"from (?:idea|concept|inception|design) (?:to|through)|autonom\w+|self[\s-]starter|"
     r"self[\s-]directed|independently)\b",
     "Include a bullet where you took something from problem to production yourself: "
     "'Owned [X] from design through launch and on-call'."),
    ("Speed and breadth (startup pace)",
     r"\b(fast[\s-]paced|startup|early[\s-]stage|seed|series [a-d]|scrappy|move fast|"
     r"many hats|high[\s-]growth|rapidly growing)\b",
     "Show shipping cadence with timelines ('shipped in 6 weeks') and range across the stack or "
     "across functions."),
    ("Comfort with ambiguity",
     r"\b(ambigu\w+|undefined|zero[\s-]to[\s-]one|0[\s-]to[\s-]1|greenfield|from scratch|"
     r"blank slate|new product|first (?:hire|engineer))\b",
     "Lead with something you built from scratch: what was unclear, what you decided, what "
     "shipped."),
    ("Experience at scale",
     r"\b(at scale|scal(?:e|able|ability|ing)|millions?|billions?|high[\s-]traffic|"
     r"large[\s-]scale|high[\s-]volume|petabytes?|terabytes?|\d+\s?[mkb]\+?\s(?:users|requests|"
     r"transactions|events))\b",
     "Put scale numbers in your bullets: users, requests/sec, data volume, money processed."),
    ("Production responsibility",
     r"\b(on[\s-]call|production (?:issues|incidents|support|systems)|incidents?|uptime|"
     r"reliab\w+|availability|operational excellence)\b",
     "Show you ran what you built: on-call, incidents resolved, uptime held, postmortems written."),
    ("Cross-functional partnership",
     r"\b(cross[\s-]functional|work(?:ing)? closely with|partner(?:ing)? with|"
     r"collaborat\w+ (?:closely )?with (?:product|design|data|sales|marketing|engineering|"
     r"stakeholders))\b",
     "Name who you worked with (product, design, sales) and what you shipped together."),
    ("Clear communication",
     r"\b(written (?:and|&) verbal|verbal (?:and|&) written|communicat\w+|articulate|explain "
     r"(?:complex|technical)|design docs?|rfcs?|documentation|present(?:ing|ations?)? to)\b",
     "Mention design docs or RFCs you wrote, talks you gave, or decisions you drove in writing."),
    ("Raising the team's level",
     r"\b(mentor\w*|coach\w*|level up|technical leadership|lead (?:a|the) team|influence|"
     r"set (?:the )?(?:technical )?direction|raise the bar|best practices)\b",
     "Count it: engineers mentored, promoted or onboarded; standards you set that others adopted."),
    ("Customer focus",
     r"\b(customer[\s-](?:facing|obsess\w*|focus\w*|centric|empathy|first)|user needs|"
     r"talk(?:ing)? to (?:customers|users)|customer feedback|user feedback)\b",
     "Tie work to customer outcomes: adoption, NPS, tickets reduced, revenue retained."),
    ("Data-driven decisions",
     r"\b(data[\s-]driven|metrics[\s-]driven|data[\s-]informed|experimentation|a/b test\w*|"
     r"measure (?:success|impact)|evidence[\s-]based)\b",
     "Every bullet should end in a measured result; mention an experiment you ran and what it "
     "changed."),
    ("Engineering quality",
     r"\b(high[\s-]quality|craft\w*|clean code|code quality|maintainab\w+|testing culture|"
     r"well[\s-]tested|code reviews?)\b",
     "Show the reviews, tests and standards you introduced, and the effect: fewer bugs, faster "
     "reviews."),
    ("Self-managed remote work",
     r"\b(remote|distributed team|async\w*|across time[\s-]zones|time[\s-]zones)\b",
     "Show you deliver without supervision: written updates, async decisions, cross-time-zone "
     "work."),
    ("Regulated environment",
     r"\b(regulat\w+|complian\w+|hipaa|soc ?2|pci|gdpr|sox|fda|finra|iso 27001)\b",
     "Name the compliance regimes you have worked under and an audit you supported."),
    ("Business impact",
     r"\b(revenue|business impact|business outcomes|bottom line|roi|profit\w*|commercial)\b",
     "Translate technical work into money or growth: $ saved, revenue enabled, conversion "
     "lifted."),
    ("Learning speed",
     r"\b(curio\w+|learn quickly|quick learner|eager to learn|growth mindset|continuous learning|"
     r"pick up new|new technologies)\b",
     "Show a time you ramped up on a new domain or technology fast and delivered with it."),
    ("Judgement on trade-offs",
     r"\b(prioriti[sz]\w*|trade[\s-]offs?|competing (?:priorities|demands)|pragmati\w+|"
     r"multiple projects|judgement|judgment)\b",
     "Show a call you made between options, why, and how it turned out."),
    ("Influence with leadership",
     r"\b(executives?|leadership team|c[\s-]suite|senior stakeholders|board|vp[\s-]level)\b",
     "Mention presenting to or persuading leaders, and the decision that followed."),
    ("Fluency with AI tools",
     r"\b(ai[\s-]assisted|ai tools|copilot|cursor|claude|chatgpt|ai[\s-]native|llm[\s-]powered|"
     r"generative ai|genai)\b",
     "Show how you used AI tools to ship faster or built AI features, with the result."),
]
SIGNAL_RE = [(n, re.compile(p, re.I), h) for n, p, h in SIGNALS]


def signals(lines: list[P.Line]) -> list[Signal]:
    out: list[tuple[int, Signal]] = []
    for name, pat, how in SIGNAL_RE:
        hits = [ln for ln in lines if ln.section != P.BENEFITS and pat.search(ln.text)]
        if not hits:
            continue
        ev = next((ln for ln in hits if ln.section != P.ABOUT), hits[0])
        out.append((len(hits), Signal(signal=name, evidence=_tidy_evidence(ev.text),
                                      how_to_show=how)))
    out.sort(key=lambda x: -x[0])
    return [s for _, s in out[:8]]


# --- The ideal resume --------------------------------------------------------------------------

KIND_OF: dict[str, str] = {}
for _kind, _names in {
    "observability": "Observability Prometheus Grafana Datadog OpenTelemetry ELK Splunk",
    "cicd": "CI/CD|GitHub Actions|GitLab CI|Jenkins|ArgoCD|Git",
    "reliability": "Site reliability engineering|On-call|Incident response|SLOs|High availability",
    "infra": "Docker|Kubernetes|Helm|Terraform|Ansible|Infrastructure as code|Serverless|Linux|"
             "TCP/IP networking",
    "cloud": "AWS|Google Cloud|Azure|Cloudflare",
    "datamodel": "Data modeling|Database design|Relational databases|NoSQL|Data warehousing|"
                 "Data quality|Data governance",
    "queue": "Message queues|Apache Kafka|RabbitMQ|Amazon SQS|Google Pub/Sub|NATS|Kinesis|"
             "Stream processing|Event-driven architecture",
    "arch": "Distributed systems|Microservices|API design|System design|REST APIs|gRPC|GraphQL|"
            "Scalability|Concurrency|Caching|High availability|Performance optimization|"
            "Domain-driven design|WebSockets|Protocol Buffers",
}.items():
    for _n in _names.replace(" ", "|").split("|") if _kind == "observability" \
            else _names.split("|"):
        KIND_OF[_n.lower()] = _kind

KIND_PROOF = {
    "observability": "Instrumented {n:12-40} services with {s}, cutting time to detect incidents "
                     "from {n:20-45} to {n:3-8} minutes",
    "cicd": "Built {s} pipelines for {n:12-40} services, cutting deploy time from {n:40-60} to "
            "{n:6-12} minutes",
    "reliability": "Owned {s} for {n:8-30} services, cutting incidents by {n:30-55}% quarter "
                   "over quarter",
    "infra": "Moved {n:15-60} production services onto {s}, cutting failed deploys by "
             "{n:40-70}% and lifting resource utilization {n:25-45}%",
    "cloud": "Ran production workloads on {s}, cutting infrastructure cost by {n:18-35}% at "
             "99.9{n:5-9}% uptime",
    "datamodel": "Applied {s} to the core data platform, cutting query time by {n:40-70}% and "
                 "supporting {n:3-10}x data growth",
    "queue": "Built event-driven flows on {s} processing {n:20-90}M events a day with no data "
             "loss",
    "arch": "Designed {s} for a platform handling {n:8-40}K requests/sec at 99.9{n:5-9}% "
            "availability",
}
SKILL_PROOF: dict[str, str] = {
    "Languages": "Built {n:6-15} production services in {s} serving {f:1.2-6.5}M requests a day",
    "Backend frameworks": "Built {n:5-12} services with {s}, serving {f:1.2-6.5}M requests a day "
                          "at {n:40-120} ms p95",
    "Frontend": "Built customer-facing features with {s} used by {n:150-900}K users, cutting load "
                "time by {n:25-50}%",
    "Mobile": "Shipped {n:10-25} features in {s} to {n:200-900}K users, holding a 99.{n:5-9}% "
              "crash-free rate",
    "Databases": "Designed {s} schemas and queries for {n:20-80} tables, cutting query time by "
                 "{n:40-70}%",
    "Testing & quality": "Introduced {s} across {n:8-25} services, raising coverage to "
                         "{n:82-92}% and cutting escaped bugs by {n:30-50}%",
    "Data engineering": "Built pipelines with {s} moving {n:200-900} GB/day into the warehouse "
                        "with {n:40-70}% fewer failures",
    "Analytics & BI": "Used {s} to answer pricing and retention questions for {n:15-60} "
                      "stakeholders, informing decisions worth ${f:1.2-4.8}M a year",
    "Machine learning & AI": "Shipped {s} work that improved precision by {n:6-14} points in "
                             "production",
    "Security & compliance": "Led {s} work that closed {n:20-60} findings ahead of an external "
                             "audit",
    "Product & delivery": "Used {s} to ship {n:8-20} features that lifted activation {n:9-24}%",
    "Design": "Designed {n:10-30} flows with {s}, lifting task success by {n:15-35}%",
    "Marketing & sales": "Ran {s} programs that generated {c:1200-4800} leads and "
                         "${f:1.5-6.5}M in pipeline",
    "Leadership & management": "Led {s} for a team of {n:6-14}: {n:3-5} promotions and "
                               "{n:90-97}% retention",
    OTHER: "Used {s} in production across {n:5-20} services, cutting manual work by {n:30-60}%",
}
YEARS_BY_LEVEL = {"Intern": 0, "Junior": 1, "Mid-level": 3, "Senior": 6, "Lead": 7,
                  "Manager": 7, "Staff/Principal": 8}


# Ways of working rather than tools: proven by how every bullet is written, not by a bullet of
# their own ("Used Stakeholder management to..." reads badly).
NO_PROOF_BULLET = {
    "Stakeholder management", "Prioritization", "KPIs", "Agile", "Product requirements",
    "Product roadmap", "Product strategy", "Project management", "Data-driven decision making",
    "Product management", "Software engineering", "Statistics", "Data analysis", "Pricing",
    "Market research", "Enterprise customers", "Product launches", "User research",
}


def _proof_kind(s: Skill) -> str:
    return KIND_OF.get(canonical(s.name).lower()) or s.category


def proof_bullet(kind: str, names: list[str], fam: Family | None = None) -> Bullet:
    """A bullet that proves skills ``names`` of one kind, with example figures."""
    tpl = KIND_PROOF.get(kind) or SKILL_PROOF.get(kind) or SKILL_PROOF[OTHER]
    if kind == "Languages" and fam and fam.name in ("Data & business analytics", "Data science"):
        tpl = "Automated {n:8-20} recurring reports in {s}, saving {n:10-25} hours a week"
    tools = [n for n in names if n != "Observability"]
    if kind == "observability" and len(tools) < len(names):
        tpl = ("Built observability for {n:12-40} services" + (" with {s}" if tools else "")
               + ", cutting time to detect incidents from {n:20-45} to {n:3-8} minutes")
        names_text = join_names(tools)
    else:
        names_text = join_names([in_sentence(n) for n in names])
    s = join_names(names)
    return Bullet(text=figures(tpl.replace("{s}", names_text), s), proves=list(names),
                  answers=f"Must-have: {s}")


CONCEPTS = {"Observability", "Mentoring", "Statistics", "Prioritization", "Accessibility",
            "Scalability", "Concurrency", "Caching", "Microservices", "Experimentation"}


def in_sentence(name: str) -> str:
    """'Data modeling' -> 'data modeling' mid-sentence; 'Kubernetes' and 'REST APIs' stay."""
    words = name.split()
    if name in CONCEPTS or (len(words) > 1 and re.fullmatch(r"[A-Z][a-z]+", words[0])
                            and all(w.islower() for w in words[1:])):
        return name[0].lower() + name[1:]
    return name


def proof_for(skill: Skill) -> Bullet:
    return proof_bullet(_proof_kind(skill), [skill.name])


def years_number(label: str) -> int:
    """'5+ years' -> 5; '3-5 years' -> 3; '' -> 0."""
    m = re.search(r"\d+", label or "")
    return int(m.group(0)) if m else 0


def _top(skills: list[Skill], wanted: list[str], n: int = 1) -> list[str]:
    """The posting's top skills that are in one of ``wanted`` (categories or skill names)."""
    picks = [s.name for s in skills if s.category in wanted or canonical(s.name) in wanted]
    return picks[:n]


def _fill(template: str, slots: dict, skills: list[Skill]) -> tuple[str, list[str]]:
    values, proves = {}, []
    for slot, (cats, default) in slots.items():
        top = _top(skills, cats)
        values[slot] = top[0] if top else default
        proves += top
    text = template.format(**values)
    text = re.sub(r"\ba ([AEIOU])", r"an \1", text)
    return text, proves


YOU_WILL = re.compile(r"(?:^|[:;]\s+|,\s+|\band\s+)you(?:'ll| will)\s+(.+)$", re.I)


def _duty_lines(lines: list[P.Line]) -> list[P.Line]:
    duties = [ln for ln in lines if ln.section == P.RESPONSIBILITIES]
    if len(duties) < 3:
        # No clear duties section: take verb-led sentences from the intro and about text, and
        # "you'll ..." clauses from anywhere ("Strong analytics: you'll define metrics").
        for ln in lines:
            if ln in duties or ln.section in (P.BENEFITS, P.PREFERRED):
                continue
            m = YOU_WILL.search(ln.text)
            if m and m.start() > 0 and to_past_tense(m.group(1))[1]:
                duties.append(replace(ln, text=m.group(1)))
            elif ln.section in (P.INTRO, P.ABOUT) and to_past_tense(ln.text)[1]:
                duties.append(ln)
    return duties


EXPERIENCE_LINE = re.compile(
    r"^(?:\d+\+?\s*years?(?: of)?\s*)?(?:(?:proven|demonstrated|strong|solid|deep|hands-on)\s+)?"
    r"(?:experience|track record|background)\s+(?:of\s+|in\s+|with\s+)?"
    r"(building|designing|developing|leading|running|scaling|shipping|owning|managing|"
    r"operating|creating|delivering|working|writing|launching|growing|driving)\b\s*(.*)$", re.I)


def skills_section_for(skills: list[Skill]) -> list[SkillGroup]:
    """Tools grouped by category, must-haves first. Soft skills are shown through bullets, not
    listed."""
    groups: dict[str, list[str]] = defaultdict(list)
    for s in sorted(skills, key=lambda s: TIER_RANK[s.tier]):
        if s.category in SOFT_CATEGORIES or s.category == "Certifications":
            continue
        if s.tier == "implied" and s.mentions < 2 and len(groups[s.category]) >= 3:
            continue
        if s.name not in groups[s.category]:
            groups[s.category].append(s.name)
    return [SkillGroup(category=c, items=v[:10]) for c, v in groups.items() if v]


def clean_title(title: str) -> str:
    """'Senior Backend Engineer (Go) - Payments Platform' -> 'Senior Backend Engineer'."""
    t = re.sub(r"\s*\([^)]*\)", "", title)
    t = re.split(r"\s*,\s+|\s+[-–—|]\s+", t)[0]
    return t.strip() or title


def ideal_resume(lines: list[P.Line], skills: list[Skill], fam: Family, title: str,
                 seniority: str, years_label: str, sigs: list[Signal],
                 domains: list[str] | None = None) -> IdealResume:
    domains = domains or []
    must = [s for s in skills if s.tier == "must"]
    tech_must = [s for s in must if s.category in TECH_CATEGORIES or s.category == OTHER]
    tech_all = [s for s in skills if s.category in TECH_CATEGORIES or s.category == OTHER]
    named = {canonical(s.name): s.name for s in skills}

    def names_in(text: str) -> list[str]:
        return list(dict.fromkeys(named.get(m.skill.name, m.skill.name)
                                  for m in find_matches(text)))

    # Headline: the title plus the 3-4 tools the posting leans on most. For roles that are not
    # tool-led (product, design, sales), the domain and the core practices instead.
    tools_first = sorted(tech_must or tech_all,
                         key=lambda s: (HEADLINE_RANK.get(s.category, 3),
                                        _proof_kind(s) in ("arch", "datamodel"), -s.mentions))
    if fam.technical:
        core = [s.name for s in tools_first[:4]] or \
               [s.name for s in must if s.category not in SOFT_CATEGORIES][:4]
    else:
        practice = [s.name for s in skills if s.category not in SOFT_CATEGORIES
                    and s.category != "Certifications"
                    and canonical(s.name) not in ("Product management", "Stakeholder management")]
        core = (domains[:1] + practice)[:4]
    head_title = clean_title(title) if title else fam.default_title
    headline = head_title + (" | " + " · ".join(core) if core else "")

    # Summary
    title_core = re.sub(r"^(senior|sr\.?|junior|jr\.?|staff|principal|lead|associate)\s+", "",
                        head_title, flags=re.I)
    level = {"Senior": "Senior ", "Staff/Principal": "Staff-level ", "Junior": "",
             "Intern": ""}.get(seniority, "")
    n_years = years_number(years_label) or YEARS_BY_LEVEL.get(seniority, 3)
    if seniority == "Intern" or not n_years:
        lead = f"{title_core} with hands-on experience"
    else:
        lead = f"{level}{title_core} with {n_years}+ years of experience"
    if fam.technical:
        with_skills = f" with {join_names([s.name for s in tools_first[:3]])}" \
            if tools_first else ""
    else:
        d = domains[0].split(" & ")[0].split(" / ")[0] if domains else ""
        with_skills = f" in {d if any(c.isupper() for c in d[1:]) else d.lower()}" if d else ""
    traits = [s.signal[0].lower() + s.signal[1:] for s in sigs
              if s.signal in TRAIT_SIGNALS][:2] or ["clear communication", "end-to-end ownership"]

    skills_section = skills_section_for(skills)

    # Bullets: one per duty, then one per requirement phrased as "experience building X",
    # then proof bullets for must-haves nothing covered yet.
    bullets: list[Bullet] = []
    used: set[str] = set()  # result phrasings already used, so bullets do not repeat
    tech_names = [s.name for s in tools_first if s.category not in ("Architecture & backend",)][:2]
    for ln in _duty_lines(lines):
        line_skills = names_in(ln.text)
        add = [] if line_skills or not fam.technical else tech_names
        text = make_bullet(ln.text, add, used)
        if not text:
            continue
        proves = list(dict.fromkeys(line_skills + [a for a in add if a in text]))
        bullets.append(Bullet(text=text, proves=proves, answers=_tidy_evidence(ln.text)))
        if len(bullets) >= 8:
            break
    for ln in lines:
        if len(bullets) >= 10:
            break
        m = EXPERIENCE_LINE.match(ln.text) if ln.section != P.BENEFITS else None
        if not m or any(b.answers == _tidy_evidence(ln.text) for b in bullets):
            continue
        text, ok = to_past_tense(drop_nice_tail(f"{m.group(1)} {m.group(2)}"))
        if not ok:
            continue
        text = shorten(text).rstrip(" .,;:")
        text = text if has_number(text) else f"{text}, {impact_for(ln.text, used)}"
        bullets.append(Bullet(text=text, proves=names_in(text), answers=_tidy_evidence(ln.text)))
    covered = {p for b in bullets for p in b.proves}
    gaps: dict[str, list[str]] = defaultdict(list)
    for s in must:
        if s.name in covered or s.category in SOFT_CATEGORIES or s.category == "Certifications" \
                or canonical(s.name) in NO_PROOF_BULLET:
            continue
        gaps[_proof_kind(s)].append(s.name)
    for kind, names in list(gaps.items())[:4]:
        bullets.append(proof_bullet(kind, names[:3], fam))

    win = next((w for b in bullets if (w := as_win(b.text))), None) or \
        figures("improved the team's core metric by {n:18-40}% within {n:6-9} months", title)
    summary = f"{lead} {fam.focus}{with_skills}. Most recently, {win}. " \
              f"Known for {join_names(traits)}."

    # Projects
    projects = []
    for tpl in fam.projects:
        desc, proves = _fill(tpl.description, tpl.slots, skills)
        projects.append(Project(title=tpl.title, description=desc,
                                proves=list(dict.fromkeys(proves))))

    certs = [s.name for s in skills if s.category == "Certifications"]
    certs += P.find_education(lines)

    if seniority in ("Intern", "Junior"):
        order = ["Headline", "Summary", "Skills", "Projects", "Experience", "Education"]
    elif seniority in ("Manager", "Staff/Principal", "Lead"):
        order = ["Headline", "Summary", "Experience (impact and leadership first)", "Skills",
                 "Education"]
    else:
        order = ["Headline", "Summary", "Skills", "Experience", "Projects", "Education"]
    if certs:
        order.append("Certifications")

    return IdealResume(headline=headline, summary=summary, skills_section=skills_section,
                       bullets=bullets, projects=projects, certifications=certs,
                       section_order=order)


HEADLINE_RANK = {
    "Languages": 0, "Backend frameworks": 1, "Frontend": 1, "Mobile": 1, "Databases": 2,
    "Messaging & streaming": 2, "Cloud & infrastructure": 2, "Machine learning & AI": 2,
    "Data engineering": 2, "Analytics & BI": 2, OTHER: 3, "DevOps & reliability": 4,
    "Testing & quality": 4, "Security & compliance": 4, "Architecture & backend": 5,
}

TRAIT_SIGNALS = {
    "End-to-end ownership", "Clear communication", "Cross-functional partnership",
    "Customer focus", "Raising the team's level", "Data-driven decisions", "Engineering quality",
    "Judgement on trade-offs", "Learning speed", "Comfort with ambiguity",
}


# --- Assembly ----------------------------------------------------------------------------------

def one_line(fam: Family, title: str, lines: list[P.Line], skills: list[Skill]) -> str:
    duty = next((ln.text for ln in _duty_lines(lines) if to_past_tense(ln.text)[1]), "")
    tools = [s.name for s in skills if s.tier == "must" and
             (s.category in TECH_CATEGORIES or s.category == OTHER)
             and s.category != "Architecture & backend"][:3] if fam.technical else []
    who = clean_title(title) if title else (fam.default_title or "This role")
    if duty:
        what = shorten(strip_lead_in(duty), 120).rstrip(" .,;:")
        what = what[0].lower() + what[1:]
        for pat, repl in PRONOUNS:
            what = pat.sub(repl, what)
        sentence = f"{who}: you would {what}"
        tools = [t for t in tools if t.lower() not in what.lower()]
    else:
        sentence = f"{who}: {fam.focus}"
    if tools:
        sentence += f", mainly with {join_names(tools)}"
    return sentence + "."


def build(jd_text: str) -> Blueprint:
    lines = P.split_lines(jd_text)
    title = P.find_title(jd_text)
    years_n, years_label = P.find_years(lines)
    seniority = P.find_seniority(title, years_n)
    body = "\n".join(ln.text for ln in lines if ln.section != P.BENEFITS)
    fam = detect_family(title, body)
    skills = extract_skills(lines)
    sigs = signals(lines)
    domains = [d for d, pat in DOMAIN_PATTERNS.items() if pat.search(body)][:4]
    role = RoleSnapshot(
        title=title or fam.default_title or "Not stated", seniority=seniority,
        role_family=fam.name, years_required=years_label, domains=domains,
        work_mode=P.find_work_mode(jd_text), one_line=one_line(fam, title, lines, skills))
    resume = ideal_resume(lines, skills, fam, title, seniority, years_label, sigs, domains)
    notes = [NUMBERS_NOTE]
    if years_label:
        notes.append(f"The posting asks for {years_label}: make your dates and titles show it "
                     "at a glance.")
    if not P.has_sections(lines):
        notes.append("The posting has no clear Requirements section, so must-haves were "
                     "inferred from wording like 'experience with' and 'strong'.")
    if len(jd_text.split()) < 80:
        notes.append("This posting is short; the blueprint is only as specific as the text.")
    bp = Blueprint(engine="offline", role=role, skills=skills,
                   keywords=keywords(lines, skills, title), signals=sigs, resume=resume,
                   notes=notes)
    from .ats import complete

    complete(bp)
    return bp


NUMBERS_NOTE = ("The numbers in the bullets are realistic examples for this role, highlighted so "
                "you can swap in your own. Use your real figures and claim only what you did; an "
                "interviewer will ask about every line.")
