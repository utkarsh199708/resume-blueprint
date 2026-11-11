"""Turning a job duty into a resume bullet: verb tense, pronouns, and a slot for the result."""

from __future__ import annotations

import hashlib
import random
import re

IRREGULAR = {
    "build": "built", "lead": "led", "write": "wrote", "run": "ran", "drive": "drove",
    "make": "made", "set": "set", "take": "took", "grow": "grew", "bring": "brought",
    "teach": "taught", "think": "thought", "keep": "kept", "spend": "spent",
    "understand": "understood", "cut": "cut", "put": "put", "sell": "sold", "meet": "met",
    "hold": "held", "become": "became", "give": "gave", "find": "found", "begin": "began",
    "choose": "chose", "deal": "dealt", "send": "sent", "speak": "spoke", "oversee": "oversaw",
    "undertake": "undertook", "rebuild": "rebuilt", "rewrite": "rewrote", "stand": "stood",
    "be": "served as", "utilize": "used", "utilise": "used", "leverage": "used",
    "participate": "contributed", "assist": "supported", "seek": "sought", "win": "won",
    "do": "did", "see": "saw", "get": "got", "have": "had",
}
DOUBLE = {"plan", "ship", "drop", "map", "scrap", "chat", "commit", "control", "step", "debug"}
VERBS = set(IRREGULAR) | {
    "design", "develop", "maintain", "implement", "architect", "create", "own", "deliver",
    "launch", "test", "debug", "deploy", "monitor", "optimize", "optimise", "improve", "scale",
    "automate", "integrate", "migrate", "refactor", "modernize", "modernise", "collaborate",
    "partner", "work", "mentor", "coach", "manage", "coordinate", "define", "plan", "prioritize",
    "prioritise", "analyze", "analyse", "research", "investigate", "troubleshoot", "support",
    "operate", "review", "document", "communicate", "present", "establish", "champion",
    "advocate", "evangelize", "identify", "evaluate", "assess", "measure", "track", "report",
    "model", "train", "fine-tune", "tune", "prototype", "conduct", "facilitate", "guide", "shape",
    "influence", "contribute", "help", "ensure", "enhance", "extend", "translate", "gather",
    "synthesize", "synthesise", "recruit", "hire", "foster", "cultivate", "negotiate", "close",
    "prospect", "engage", "onboard", "retain", "configure", "administer", "secure", "harden",
    "audit", "respond", "resolve", "handle", "provide", "produce", "craft", "author", "curate",
    "execute", "streamline", "reduce", "increase", "accelerate", "standardize", "standardise",
    "instrument", "interview", "liaise", "align", "collect", "clean", "visualize", "visualise",
    "forecast", "query", "spearhead", "pioneer", "innovate", "invent", "solve", "explore",
    "experiment", "iterate", "validate", "verify", "apply", "use", "serve", "act", "ship",
    "publish", "promote", "nurture", "convert", "generate", "source",
    "qualify", "pitch", "demo", "renew", "upsell", "expand", "inspire", "empower", "unblock",
    "oversee", "steer", "orchestrate", "direct", "supervise", "compile", "prepare", "process",
    "reconcile", "draft", "edit", "illustrate", "wireframe", "sketch", "write",
    "benchmark", "profile", "patch", "upgrade", "provision", "containerize", "package", "release",
    "detect", "prevent", "protect", "mitigate", "remediate", "triage", "escalate",
    "educate", "enable", "equip", "simplify", "consolidate", "rework", "redesign",
    "reimagine", "rethink", "refine", "polish", "embed", "join", "connect", "think", "learn", "adopt", "introduce", "roll", "stand", "kick", "drive", "set",
}


def past(verb: str) -> str:
    v = verb.lower()
    if v in IRREGULAR:
        return IRREGULAR[v]
    if v.endswith("e"):
        return v + "d"
    if v.endswith("y") and len(v) > 1 and v[-2] not in "aeiou":
        return v[:-1] + "ied"
    if v in DOUBLE:
        return v + v[-1] + "ed"
    return v + "ed"


def _ing(v: str) -> str:
    if v.endswith("ie"):
        return v[:-2] + "ying"
    if v.endswith("e") and not v.endswith(("ee", "ye", "oe")) and v != "be":
        return v[:-1] + "ing"
    if v in DOUBLE or v in {"run", "set", "get", "put", "cut", "begin", "win"}:
        return v + v[-1] + "ing"
    return v + "ing"


def _s(v: str) -> str:
    if v.endswith(("s", "sh", "ch", "x", "z")):
        return v + "es"
    if v.endswith("y") and v[-2] not in "aeiou":
        return v[:-1] + "ies"
    return v + "s"


FORMS: dict[str, str] = {}  # every form of a known verb (base, -s, -ing, past) -> base
for _v in VERBS:
    for _f in (_v, _ing(_v), _s(_v)):
        FORMS.setdefault(_f, _v)
for _v in VERBS:
    if " " not in past(_v):
        FORMS.setdefault(past(_v), _v)  # "Profiled ..." is already a resume bullet
FORMS["is"] = FORMS["are"] = "be"


def base_verb(word: str) -> str | None:
    w = word.lower().strip(",;:")
    if "/" in w:
        return None
    return FORMS.get(w)


LEAD_INS = re.compile(
    r"^(?:in this role,?\s*)?(?:as (?:a|an|our) [^,]{2,40},\s*)?"
    r"(?:you(?:'ll| will| would|'d)?|we expect you to|the (?:ideal )?candidate will|this "
    r"(?:person|role) will|will|be (?:responsible|accountable) for|responsible for|"
    r"you are (?:responsible|accountable) for|help us|our ideal candidate will|"
    r"expected to|tasked with|ability to|able to|opportunity to|chance to)\s+",
    re.I)
PRONOUNS = [(re.compile(r"\bour\b", re.I), "the"), (re.compile(r"\byour\b", re.I), "the"),
            (re.compile(r"\bwe\b", re.I), "the team"), (re.compile(r"\bus\b"), "the team")]


def strip_lead_in(text: str) -> str:
    prev = None
    s = text.strip().rstrip(".;:")
    while prev != s:
        prev = s
        s = LEAD_INS.sub("", s, count=1).strip()
    return s


def to_past_tense(text: str) -> tuple[str, bool]:
    """('Designed, built and maintained ...', True) or (text, False) when it is not verb-led."""
    s = strip_lead_in(text)
    for pat, repl in PRONOUNS:
        s = pat.sub(repl, s)
    tokens = s.split()
    if not tokens:
        return text, False
    # "Closely collaborate with" -> "Collaborated closely with"
    if len(tokens) > 1 and tokens[0].lower().endswith("ly") and base_verb(tokens[1]):
        tokens[0], tokens[1] = tokens[1], tokens[0].lower()
    if not base_verb(tokens[0].split("/")[0]) and not ("/" in tokens[0] and all(
            base_verb(p) for p in tokens[0].split("/"))):
        return s, False
    out: list[str] = []
    i = 0
    expecting_verb = True
    while i < len(tokens):
        tok = tokens[i]
        core = tok.rstrip(",;")
        trail = tok[len(core):]
        if expecting_verb:
            parts = core.split("/")
            if all(base_verb(p) for p in parts):
                out.append("/".join(past(base_verb(p)) for p in parts) + trail)
                expecting_verb = False
                i += 1
                # Coordinated verbs: "design, build, and maintain"
                if trail == "," or (i < len(tokens) and tokens[i].lower() in ("and", "or", "&")):
                    if i < len(tokens) and tokens[i].lower() in ("and", "or", "&"):
                        out.append("and")
                        i += 1
                    nxt = tokens[i].rstrip(",;") if i < len(tokens) else ""
                    if nxt.lower() in ("and", "or"):
                        out.append("and")
                        i += 1
                        nxt = tokens[i].rstrip(",;") if i < len(tokens) else ""
                    if nxt and all(base_verb(p) for p in nxt.split("/")):
                        expecting_verb = True
                continue
        out.append(tok)
        i += 1
        expecting_verb = False
    res = " ".join(out)
    res = re.sub(r"\bserved as as\b", "served as", res)
    res = re.sub(r"\b(?:you(?:'ll| will)|we(?:'ll| will))\s+", "", res, flags=re.I)
    res = re.sub(r"(,? and )(work|partner) with\b",
                 lambda m: m.group(1) + m.group(2) + "ed with", res)
    # A second verb later in the duty: "Mentor engineers and raise the bar". Only verbs that are
    # rarely nouns, so "product and design" stays as it is.
    res = re.sub(r"(,? and |, )(" + "|".join(LATER_VERBS) + r")\b",
                 lambda m: m.group(1) + past(m.group(2)), res)
    return res[0].upper() + res[1:], True


LATER_VERBS = sorted({
    "raise", "drive", "ensure", "improve", "deliver", "maintain", "implement", "develop",
    "optimize", "optimise", "build", "own", "partner", "collaborate", "contribute", "champion",
    "establish", "define", "identify", "mentor", "create", "launch", "write", "automate", "reduce",
    "increase", "influence", "communicate", "present", "evaluate", "manage", "coordinate",
    "prioritize", "prioritise", "translate", "shape", "grow", "deploy", "monitor", "analyze",
    "analyse", "recommend", "size", "investigate", "resolve", "debug", "run", "ship", "lead",
    "help", "foster", "make", "set", "take", "turn", "keep", "use", "talk", "listen", "learn",
}, key=len, reverse=True)
VERBS |= {"talk", "listen", "size", "recommend", "raise"}
for _v in ("talk", "listen", "size", "recommend", "raise"):
    for _f in (_v, _ing(_v), _s(_v)):
        FORMS.setdefault(_f, _v)

NICE_TAIL = re.compile(
    r",?\s+(?:is|are|would be|will be)\s+(?:a\s+(?:big\s+|huge\s+)?plus|preferred|desired|"
    r"nice to have|a bonus|an advantage|beneficial|required|a must)\b.*$|,?\s+as is\b.*$", re.I)


def drop_nice_tail(text: str) -> str:
    """'with enterprise customers is a plus, as is X' -> 'with enterprise customers'."""
    return NICE_TAIL.sub("", text).strip()


# Result phrases with realistic example figures. "{n:35-62}" is a whole number in that range,
# "{f:1.2-4.8}" one with a decimal, "{c:400-2400}" one with a thousands comma. The figure is
# picked from a hash of the text, so the same posting always gets the same numbers.
IMPACT: list[tuple[str, list[str]]] = [
    (r"\b(web vitals|page loads?|load times?|bundle size)\b", [
        "cutting load time by {n:25-50}% for {n:150-900}K users",
        "taking Largest Contentful Paint from {f:3.5-5.5}s to {f:1.2-2.2}s"]),
    (r"\b(ui|user interfaces?|components?|front[\s-]?end|accessib\w*|css|responsive)\b", [
        "lifting Lighthouse accessibility scores from {n:60-75} to {n:95-100}",
        "reused across {n:12-40} product screens",
        "cutting UI bugs by {n:30-55}% release over release"]),
    (r"\b(latency|performance|optimi[sz]\w*|throughput|speed up|load times?)\b", [
        "cutting p95 latency by {n:35-62}% at {n:8-40}K requests/sec",
        "taking p99 latency from {n:300-600} ms to {n:60-150} ms",
        "raising throughput {n:2-5}x on the same hardware"]),
    (r"\b(reliab\w*|availability|uptime|incidents?|on[\s-]call|resilien\w*|fault|slos?)\b", [
        "holding 99.9{n:5-9}% availability and cutting incidents by {n:30-55}%",
        "cutting Sev-1 incidents from {n:6-12} to {n:1-2} a quarter",
        "cutting mean time to recovery from {n:40-90} to {n:8-20} minutes"]),
    (r"\b(secur\w*|vulnerab\w*|compliance|audits?|threats?)\b", [
        "closing {n:20-60} vulnerabilities and passing {n:2-3} external audits with no major "
        "findings",
        "cutting critical findings by {n:60-90}% in {n:2-4} quarters"]),
    (r"\b(migrat\w*|legacy|moderni[sz]\w*|refactor\w*|re-?architect\w*|rewrite)\b", [
        "with zero downtime, retiring {n:4-12} legacy services",
        "moving {n:20-80}M records with zero data loss and {n:25-40}% lower running cost"]),
    (r"\b(a/b tests?|experiments?|experimentation)\b", [
        "turning {n:12-30} experiments into shipped changes that lifted conversion {n:4-11}%",
        "running {n:20-45} experiments a quarter with a {n:25-40}% win rate"]),
    (r"\b(models?|machine learning|ml|predict\w*|recommendation (?:systems?|engines?)|"
     r"recommender\w*|llms?|ai|fine[\s-]tun\w*)\b", [
        "improving precision by {n:6-14} points over the baseline",
        "lifting recall by {n:8-18}% while cutting inference cost {n:30-50}%"]),
    (r"\b(data quality|tracking|instrumentation|data issues)\b", [
        "cutting data-quality incidents by {n:40-70}% across {n:150-400} tables and events",
        "bringing tracking coverage to {n:95-99}% of key events"]),
    (r"\b(automat\w*|ci/cd|ci|deploy\w*|release|infrastructure|terraform|kubernetes|cloud)\b", [
        "cutting deploy time from {n:40-60} to {n:6-12} minutes and enabling {n:15-40} releases "
        "a week",
        "saving {n:10-30} engineer-hours a week"]),
    (r"\b(tests?|testing|code quality|quality assurance|qa|bugs?|defects?|code reviews?)\b", [
        "raising test coverage from {n:38-55}% to {n:82-92}% and cutting escaped bugs by "
        "{n:30-50}%",
        "cutting escaped defects by {n:35-60}% over {n:2-3} quarters"]),
    (r"\b(mentor\w*|coach\w*|hir(e|ing)|onboard\w*|grow (?:the )?team|team members|"
     r"engineers)\b", [
        "growing a team of {n:5-9}, with {n:2-4} promoted within {n:12-18} months",
        "onboarding {n:6-12} engineers to their first production change in under {n:2-3} weeks"]),
    (r"\b(dashboards?|reports?|reporting|insights?|analy[sz]\w*|kpis?|metrics|findings|"
     r"ad hoc|questions|sql|queries|churn|drivers)\b", [
        "informing decisions worth ${f:1.2-4.8}M a year for {n:15-60} stakeholders",
        "cutting time to insight from {n:3-5} days to {n:2-6} hours",
        "uncovering ${f:0.8-3.5}M in annual revenue opportunities",
        "used weekly by {n:40-200} people across {n:4-9} teams"]),
    (r"\b(pipelines?|etl|elt|warehouse|ingest\w*|data platform|data models?)\b", [
        "processing {n:200-900} GB/day with {n:40-70}% fewer failed runs",
        "cutting pipeline run time from {n:4-8} hours to {n:20-50} minutes"]),
    (r"\b(scal\w*|millions?|high[\s-]traffic|large[\s-]scale|volume)\b", [
        "scaling to {n:2-9}M users and {n:10-60}K requests/sec",
        "absorbing {n:5-20}x traffic growth with no added headcount"]),
    (r"\b(customers?|users?|growth|revenue|conversion|retention|engagement|adoption|funnel)\b", [
        "lifting {metric} by {n:8-24}% across {n:120-900}K users",
        "adding ${f:1.2-6.5}M in annual recurring revenue"]),
    (r"\b(cost|budget|spend)\b", [
        "saving ${n:120-480}K a year",
        "cutting cloud spend by {n:22-40}% (${n:150-600}K a year)"]),
    (r"\b(quota|deals?|closing|account executive|prospect\w*|territory)\b", [
        "beating quota by {n:12-35}% for {n:3-6} straight quarters",
        "closing ${f:1.2-4.8}M in new annual contract value"]),
    (r"\b(seo|organic|content)\b", [
        "growing organic traffic {n:40-150}% in {n:2-4} quarters",
        "ranking {n:15-60} pages on the first page of Google for target keywords"]),
    (r"\b(campaigns?|brand|leads?|pipeline|paid|ads)\b", [
        "generating {c:1200-4800} qualified leads and ${f:1.5-6.5}M in pipeline in 12 months",
        "cutting cost per acquisition by {n:20-45}% at {n:2-4}x the spend"]),
    (r"\b(roadmaps?|prioriti[sz]\w*|strategy|requirements|prds?|launch\w*)\b", [
        "shipping {n:8-20} features on schedule that lifted activation {n:9-24}%",
        "growing weekly active users {n:20-60}% in {n:2-4} quarters"]),
    (r"\b(collaborat\w*|partner\w*|cross[\s-]functional|stakeholders?|product|design)\b", [
        "delivering {n:6-14} launches on schedule",
        "cutting handoff delays by {n:30-50}% across {n:3-6} teams"]),
    (r"\b(document\w*|rfcs?|design docs?|write|writing|communicat\w*)\b", [
        "adopted by {n:4-12} teams",
        "cutting onboarding time from {n:4-6} weeks to {n:5-9} days"]),
    (r"\b(apis?|services?|systems?|features?|platforms?|applications?|apps?)\b", [
        "serving {f:1.5-9.5}M requests a day for {n:150-900}K users",
        "used by {n:40-300} internal and external integrations"]),
]
IMPACT_RE = [(re.compile(p, re.I), v) for p, v in IMPACT]
DEFAULT_IMPACT = ["improving the team's core metric by {n:18-40}% within {n:6-9} months",
                  "cutting turnaround time by {n:25-50}% in {n:2-3} quarters"]
METRICS = ("retention", "revenue", "engagement", "adoption", "conversion")
SLOT = re.compile(r"\{([nfc]):(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\}")


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:12], 16)


def figures(template: str, seed: str) -> str:
    """Fill each {n:lo-hi} slot with a figure in range, the same one every time for ``seed``."""
    rng = random.Random(_seed(f"{seed}|{template}"))

    def pick(m: re.Match) -> str:
        kind, lo, hi = m.group(1), float(m.group(2)), float(m.group(3))
        if kind == "f":
            return f"{rng.uniform(lo, hi):.1f}"
        value = rng.randint(int(lo), int(hi))
        if kind == "c":
            return f"{round(value, -2):,}"
        return str(value)

    return SLOT.sub(pick, template)


def _echoes(phrase: str, text: str) -> bool:
    words = re.findall(r"[a-z]{4,}", SLOT.sub(" ", phrase).lower())
    low = text.lower()
    return any(f"{a} {b}" in low for a, b in zip(words, words[1:], strict=False))


def impact_for(text: str, used: set[str] | None = None) -> str:
    """A result clause for ``text`` with example figures: 'cutting p95 latency by 41% at ...'.

    ``used`` holds the phrasings already in this resume, so two bullets do not end the same way.
    """
    groups = [v for pat, v in IMPACT_RE if pat.search(text)] + [DEFAULT_IMPACT]
    start = _seed(text)
    options = [g[(start + i) % len(g)] for g in groups for i in range(len(g))]
    fresh = [o for o in options if used is None or o not in used] or options
    # Not one that repeats the duty's own words ("grow organic traffic, growing organic traffic").
    phrase = next((o for o in fresh if not _echoes(o, text)), fresh[0])
    if used is not None:
        used.add(phrase)
    low = text.lower()
    phrase = phrase.replace("{metric}", next((m for m in METRICS if m in low), "conversion"))
    return figures(phrase, text)


# The first word of a result clause, for turning it into a sentence: "cutting" -> "cut".
ING_PAST = {
    "cutting": "cut", "holding": "held", "closing": "closed", "turning": "turned",
    "improving": "improved", "raising": "raised", "growing": "grew", "informing": "informed",
    "processing": "processed", "scaling": "scaled", "lifting": "lifted", "saving": "saved",
    "generating": "generated", "shipping": "shipped", "delivering": "delivered",
    "serving": "served", "taking": "took", "moving": "moved", "running": "ran",
    "bringing": "brought", "onboarding": "onboarded", "uncovering": "uncovered",
    "absorbing": "absorbed", "adding": "added", "beating": "beat", "ranking": "ranked",
}


def as_win(bullet: str) -> str | None:
    """'Built X, cutting p95 latency by 41%' -> 'cut p95 latency by 41%' (for the summary)."""
    head, sep, tail = bullet.rpartition(", ")
    first = tail.split(" ", 1)[0]
    if not sep or first not in ING_PAST or not re.search(r"\d", tail):
        return None
    return ING_PAST[first] + tail[len(first):]


NUMBER = re.compile(r"(?<![\w.])[$£€₹]?\d[\d,]*(?:\.\d+)?(?:%|[KMB](?![A-Za-z])|x(?![A-Za-z]))?")


def has_number(text: str) -> bool:
    return bool(NUMBER.search(text))


BUILD_VERBS = {"designed", "built", "developed", "implemented", "architected", "created",
               "wrote", "shipped", "delivered", "launched", "migrated", "automated", "optimized",
               "optimised", "scaled", "integrated", "maintained", "deployed", "refactored"}


def shorten(text: str, limit: int = 150) -> str:
    if len(text) <= limit:
        return text
    for sep in ("; ", " — ", " – ", ": ", ". ", " (e.g", " such as ", " including "):
        k = text.find(sep, 50)
        if 0 < k <= limit:
            return text[:k].rstrip(" ,")
    k = text.rfind(", ", 50, limit)
    if k > 0:
        return text[:k]
    k = text.rfind(" ", 50, limit)
    return text[: k if k > 0 else limit]


def join_names(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def make_bullet(duty: str, tech: list[str], used: set[str] | None = None) -> str | None:
    """A resume bullet that answers ``duty``; ``tech`` is added when the duty names no tool."""
    text, ok = to_past_tense(duty)
    if not ok:
        return None
    text = shorten(text).rstrip(" .,;:")
    # A duty with its own numbers ("scale from 300 to 3,000 TPS") already states the result the
    # employer wants to see; any other duty gets a result clause with example figures.
    first = text.split()[0].lower().rstrip(",")
    tech = [t for t in tech if t.lower() not in text.lower()]
    if tech and first in BUILD_VERBS:
        text += f" using {join_names(tech)}"
    return text if has_number(text) else f"{text}, {impact_for(duty, used)}"


WEAK_OPENERS = re.compile(
    r"^(?:was |were )?(responsible for|in charge of|worked on|working on|helped( with| to)?|"
    r"assisted( with| in)?|involved in|participated in|duties included|tasked with|handled|"
    r"part of|member of|exposure to|familiar with|did|doing)\b\s*", re.I)


def strengthen(line: str, used: set[str] | None = None) -> str:
    """Rewrite a weak resume line into an action-verb bullet that ends in a measured result."""
    s = BULLET_MARK.sub("", line).strip().rstrip(". ")
    weak = bool(WEAK_OPENERS.match(s))
    s = WEAK_OPENERS.sub("", s, count=1)
    text, ok = to_past_tense(s)
    if not ok:
        if not weak:
            return line.strip()  # not a sentence we can safely rewrite (a skills list, a title)
        keep_case = len(s) > 1 and (s[1].isupper() or s[1].isdigit())  # "SQL", "AWS", "S3"
        text = "Delivered " + (s if keep_case or not s else s[0].lower() + s[1:])
    return text if has_number(text) else f"{text}, {impact_for(text, used)}"


BULLET_MARK = re.compile(r"^\s*(?:[-*•·▪◦‣–—►●○]|\d{1,2}[.)])\s+")
