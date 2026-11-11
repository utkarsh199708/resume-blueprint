"""Read a job description: split it into sections and lines, and tag what each line is for."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Section kinds, in the order they matter for a resume.
REQUIREMENTS = "requirements"
PREFERRED = "preferred"
RESPONSIBILITIES = "responsibilities"
ABOUT = "about"
BENEFITS = "benefits"
INTRO = "intro"

HEADERS: list[tuple[str, re.Pattern]] = [
    (PREFERRED, re.compile(
        r"^(nice[\s-]to[\s-]haves?|preferred( qualifications| skills| experience)?|bonus( points)?|"
        r"pluses|plus|good[\s-]to[\s-]have|desired( skills| qualifications)?|"
        r"(it'?s |it would be |it is )?(a )?(big |huge )?(great|nice|bonus|plus) if( you)?( have)?|"
        r"extra credit|"
        r"ways to stand out|what would make you stand out|stand out if|"
        r"additional (skills|qualifications)|desirable)\b", re.I)),
    (REQUIREMENTS, re.compile(
        r"^(requirements|required( skills| qualifications| experience)?|qualifications|"
        r"(minimum|basic|key|core|essential) (qualifications|requirements|skills)|"
        r"must[\s-]haves?|skills( and| &) (experience|qualifications)|skills|"
        r"what (you'?ll|you will|you) (need|bring|have)|what we'?re looking for|"
        r"what we look for|who you are|about you|you (have|bring|are|might be)|"
        r"your (background|experience|skills|profile)|experience|ideal candidate|"
        r"the ideal candidate|we'?re looking for|we are looking for|is this you|"
        r"you'?ll be a great fit if|you may be a (good|great) fit if|what it takes|"
        r"to succeed in this role|knowledge,? skills,? (and|&) abilities|competencies)\b", re.I)),
    (RESPONSIBILITIES, re.compile(
        r"^(responsibilities|key responsibilities|duties|(your|the) (role|impact|mission)|"
        r"what (you'?ll|you will) (do|be doing|work on|own|achieve)|what the job involves|"
        r"in this role,? you( will|'?ll)?|day[\s-]to[\s-]day|a day in the life|"
        r"what you'?ll be doing|you will|you'?ll|job description|role description|"
        r"the opportunity|about the role|the job|position summary|role overview|"
        r"overview of the role|your responsibilities|scope)\b", re.I)),
    (BENEFITS, re.compile(
        r"^(benefits|perks|what we offer|we offer|compensation|salary|pay range|"
        r"why (join|work)|why you'?ll love|what'?s in it for you|our benefits|total rewards|"
        r"equal (opportunity|employment)|eeo|diversity|accommodations|location and|"
        r"how to apply|application process|interview process|hiring process|"
        r"the (salary|base pay)|base salary)\b", re.I)),
    (ABOUT, re.compile(
        r"^(about (us|the company|the team|[A-Z][\w&.\- ]{1,40})|who we are|our (team|mission|"
        r"story|company|values)|the team|company overview|our culture)\b", re.I)),
]

BULLET = re.compile(r"^\s*(?:[-*•·▪◦‣–—►●○]|\d{1,2}[.)]|[a-z][.)])\s+")
NICE_CUES = re.compile(
    r"\b(nice[\s-]to[\s-]have|a (big |huge )?plus|is a plus|are a plus|bonus|preferred|"
    r"preferably|ideally|desirable|desired|good to have|would be (great|nice|a plus)|great if|"
    r"an advantage|advantageous|not required|optional|extra credit|helpful|"
    r"is beneficial|would be beneficial|appreciated)\b", re.I)
MUST_CUES = re.compile(
    r"\b(required|requirement|must|need to have|you have|proven|strong|deep|expert|expertise|"
    r"extensive|solid|proficien\w*|advanced|hands-on|demonstrated|track record|"
    r"\d+\+?\s*(?:-\s*\d+\s*)?years?)\b", re.I)
MID_NICE = re.compile(r"(?:,|;|\s\()\s*(?=(?:ideally|preferably|bonus points|and bonus)\b)", re.I)
REQUIREMENT_LIKE = re.compile(
    r"\b(experience (with|in|building|designing|leading|working)|years|knowledge of|"
    r"proficien\w*|familiar\w*|understanding of|background in|expertise|skilled|ability to|"
    r"degree|fluency|fluent|comfortable with|track record)\b", re.I)


@dataclass
class Line:
    text: str          # cleaned text, bullet marker removed
    raw: str           # as it appeared
    section: str       # one of the section kinds
    is_bullet: bool
    header: str        # the header it sits under ('' when none)

    @property
    def nice(self) -> bool:
        return bool(NICE_CUES.search(self.text))

    @property
    def must(self) -> bool:
        return bool(MUST_CUES.search(self.text))


def normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    # A pasted list sometimes arrives on one line: "• one • two • three".
    text = re.sub(r"\s+([•●▪►])\s+", r"\n\1 ", text)
    return text


NOT_A_HEADER_TAIL = {"with", "in", "of", "on", "for", "to", "building", "using", "as", "at", "is",
                     "are", "and", "or", "the", "a", "an", "working", "leading", "designing"}


def _header_kind(line: str) -> tuple[str | None, str]:
    """(kind, rest) when ``line`` is a section header; rest is any text after a colon."""
    if BULLET.match(line) and not line.lstrip().startswith(("**", "__")):
        return None, ""  # "* Experience with dbt" is a list item, never a header
    s = line.strip().strip("#*_ ").strip()
    if not s or len(s) > 90:
        return None, ""
    head, rest = s, ""
    if ":" in s:
        head, rest = s.split(":", 1)
        head = head.strip().strip("*_ ")
        rest = rest.strip()
        if len(head) > 60:
            return None, ""
    elif len(s.split()) > 9 or s.endswith("."):
        return None, ""
    head_clean = re.sub(r"[^\w\s'&/,-]", "", head).strip()
    for kind, pat in HEADERS:
        m = pat.match(head_clean)
        if not m:
            continue
        # "Experience with Go" or "You have 5+ years of Go" is a line, not a header: a header
        # without a colon is the matched phrase plus at most two more words.
        tail = head_clean[m.end():].split()
        if ":" not in s and (len(tail) > 2 or (tail and tail[0].lower() in NOT_A_HEADER_TAIL)):
            return None, ""
        return kind, rest
    return None, ""


def split_lines(text: str) -> list[Line]:
    text = normalise(text)
    lines: list[Line] = []
    section, header = INTRO, ""
    for raw in text.split("\n"):
        if not raw.strip():
            continue
        kind, rest = _header_kind(raw)
        if kind:
            section = kind
            header = raw.strip().strip("#*_ :")
            if not rest:
                continue
            raw = rest
        is_bullet = bool(BULLET.match(raw))
        clean = BULLET.sub("", raw).strip().strip("*_").strip()
        if not clean:
            continue
        # Long paragraphs: one sentence per line, so evidence quotes stay short.
        parts = [clean] if len(clean) < 160 else re.split(r"(?<=[.!?])\s+(?=[A-Z])", clean)
        # "5+ years of PM experience, ideally with developer products": the first half is
        # required, only the second is a preference.
        parts = [p for part in parts for p in MID_NICE.split(part)]
        for part in parts:
            part = part.strip()
            if part:
                lines.append(Line(part, raw, section, is_bullet, header))
    return lines


def has_sections(lines: list[Line]) -> bool:
    return any(ln.section in (REQUIREMENTS, PREFERRED, RESPONSIBILITIES) for ln in lines)


def line_tier(line: Line, structured: bool) -> str:
    """What a line asks for: 'must', 'nice', 'implied', or 'ignore' (benefits, legal text)."""
    if line.section == BENEFITS:
        return "ignore"
    if line.nice:
        return "nice"
    if line.section == PREFERRED:
        return "nice"
    if line.section == REQUIREMENTS:
        return "must"
    if not structured and (line.must or REQUIREMENT_LIKE.search(line.text)):
        return "must"
    if line.section in (INTRO, RESPONSIBILITIES) and line.must and \
            REQUIREMENT_LIKE.search(line.text):
        return "must"
    return "implied"


# --- Role facts -------------------------------------------------------------------------------

ROLE_NOUNS = (
    r"engineer|developer|programmer|architect|scientist|analyst|designer|manager|lead|director|"
    r"head of|vp|specialist|consultant|administrator|admin|intern|coordinator|associate|"
    r"representative|executive|officer|researcher|strategist|writer|marketer|recruiter|sre|"
    r"devops|technician|owner|partner|advocate|evangelist|accountant|editor|producer"
)
TITLE_LABEL = re.compile(r"^\s*(?:job title|title|position|role|job)\s*[:\-–]\s*(.+)$", re.I)
TITLE_IN_TEXT = re.compile(
    r"(?:hiring|looking for|seeking|searching for|join us as|as (?:a|an|our))\s+(?:an?\s+|our\s+)?"
    r"((?:[A-Z][\w+#/.-]*\s+){0,5}?(?:" + ROLE_NOUNS.replace("|", "s?|") + r"s?))\b", re.I)
ROLE_NOUN_RE = re.compile(rf"\b({ROLE_NOUNS})s?\b", re.I)


def find_title(text: str) -> str:
    raw_lines = [ln.strip().strip("#*_ ") for ln in normalise(text).split("\n") if ln.strip()]
    for ln in raw_lines[:15]:
        m = TITLE_LABEL.match(ln)
        if m and ROLE_NOUN_RE.search(m.group(1)):
            return _tidy_title(m.group(1))
    for ln in raw_lines[:6]:
        if len(ln) <= 80 and ROLE_NOUN_RE.search(ln) and not ln.endswith(".") \
                and len(ln.split()) <= 10 and not _header_kind(ln)[0]:
            return _tidy_title(ln)
    m = TITLE_IN_TEXT.search(text)
    if m:
        return _tidy_title(m.group(1))
    return ""


def _tidy_title(t: str) -> str:
    t = re.sub(r"\s*[|•]\s*.*$", "", t)                        # "Title | Company | City"
    t = re.sub(r"\s*\((?:remote|hybrid|on-?site|[A-Z][a-z]+(?:, ?[A-Z]{2})?)\)\s*$", "", t, flags=re.I)
    t = re.sub(r"^(we'?re hiring:?|hiring:?|job:?)\s*", "", t, flags=re.I)
    t = re.sub(r"\s+at\s+[A-Z][\w&.\- ]+$", "", t)
    return t.strip(" -–—:,")


SENIORITY_WORDS = [
    ("Intern", r"\b(intern|internship|co-?op|apprentice)\b"),
    ("Staff/Principal", r"\b(staff|principal|distinguished|fellow)\b"),
    ("Manager", r"\b(manager|head of|director|vp|vice president|chief)\b"),
    ("Lead", r"\b(lead|team lead|tech lead)\b"),
    ("Senior", r"\b(senior|sr\.?|iii|level 3|l5)\b"),
    ("Junior", r"\b(junior|jr\.?|entry[\s-]level|graduate|new grad|associate|early career|"
               r"i\b(?!\w))"),
    ("Mid-level", r"\b(mid[\s-]?level|intermediate|ii\b)"),
]
YEARS = re.compile(
    r"(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*(\d{1,2}))?\s*\+?\s*(?:years?|yrs?)\b", re.I)


def find_years(lines: list[Line]) -> tuple[int | None, str]:
    """The largest minimum years of experience the posting asks for, e.g. (5, '5+ years')."""
    best: tuple[int, str] | None = None
    for ln in lines:
        if ln.section == BENEFITS:
            continue
        for m in YEARS.finditer(ln.text):
            n = int(m.group(1))
            if n == 0 or n > 25:
                continue
            tail = ln.text[m.end(): m.end() + 80].lower()
            head = ln.text[max(0, m.start() - 40): m.start()].lower()
            # "5+ years of experience", or in a requirements list "4+ years in B2B marketing"
            # and "2+ years of Python" (but not "10 years in business" in the about text).
            named = "experience" in tail + head or "exp" in tail or "background" in tail
            listed = ln.section in (REQUIREMENTS, PREFERRED) and \
                re.match(r"\s*(?:of|in|with|working|building|running|leading)\b", tail)
            if not (named or listed):
                continue
            label = f"{n}-{m.group(2)} years" if m.group(2) else f"{n}+ years"
            if best is None or n > best[0]:
                best = (n, label)
    return (best[0], best[1]) if best else (None, "")


def find_seniority(title: str, years: int | None) -> str:
    t = title.lower()
    for level, pat in SENIORITY_WORDS:
        if re.search(pat, t):
            # A product, project or account manager is a role, not a people-manager level.
            if level == "Manager" and re.search(
                    r"\b(product|project|program|account|marketing|community|success|content|"
                    r"social media|office|partner|campaign)\s+manager", t) \
                    and not re.search(r"\b(director|head of|vp|group)\b", t):
                continue
            if level == "Lead" and re.search(r"\blead (generation|gen)\b", t):
                continue
            return level
    if years is None:
        return "Mid-level"
    if years < 2:
        return "Junior"
    if years < 5:
        return "Mid-level"
    if years < 8:
        return "Senior"
    return "Staff/Principal"


WORK_MODE = [
    ("Remote", r"\b(fully remote|100% remote|remote[\s-]first|remote[\s-]friendly|remote\b"
               r"(?!\s+(?:sensing|control)))"),
    ("Hybrid", r"\bhybrid\b"),
    ("On-site", r"\b(on[\s-]?site|in[\s-]office|in the office|office[\s-]based)\b"),
]


def find_work_mode(text: str) -> str:
    found = [mode for mode, pat in WORK_MODE if re.search(pat, text, re.I)]
    if "Hybrid" in found:
        return "Hybrid"
    if found:
        return found[0]
    return ""


EDUCATION_WORDS = re.compile(
    r"\b(bachelor'?s|master'?s|ph\.?\s?d|doctorate|undergraduate|university degree|"
    r"college degree|degree in|degree or|degree,|related degree|technical degree|graduate degree)",
    re.I)
EDUCATION_ABBR = re.compile(
    r"(?<![A-Za-z])(BS|B\.S\.|BSc|B\.Sc\.?|BA|B\.A\.|BE|B\.E\.|BTech|B\.Tech\.?|MS|M\.S\.|MSc|"
    r"M\.Sc\.?|MA|M\.A\.|MTech|M\.Tech\.?|MBA|PhD|Ph\.D\.?)(?![A-Za-z])")


def find_education(lines: list[Line]) -> list[str]:
    out = []
    for ln in lines:
        if ln.section == BENEFITS:
            continue
        if EDUCATION_WORDS.search(ln.text) or EDUCATION_ABBR.search(ln.text):
            out.append(ln.text.rstrip("."))
    return out[:3]
