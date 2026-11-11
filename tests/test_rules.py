"""The rules engine: matching, parsing, and writing."""

from pathlib import Path

import pytest

from blueprint import parse as P
from blueprint.offline import build
from blueprint.taxonomy import find_matches
from blueprint.writing import NUMBER, make_bullet, strengthen, to_past_tense

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def names(text: str) -> list[str]:
    return [m.skill.name for m in find_matches(text)]


@pytest.mark.parametrize("text, expected", [
    ("Experience with Go/Python and k8s", ["Go", "Python", "Kubernetes"]),
    ("Go above and beyond. Our go-to-market team.", ["Go-to-market"]),
    ("We are a Series C startup", []),
    ("C/C++ and C# welcome", ["C", "C++", "C#"]),
    ("React Native is a plus", ["React Native"]),
    ("Spring Boot and SQL Server", ["Spring Boot", "SQL Server"]),
    ("UI/UX sense", ["UX design"]),
    ("We're hiring! You'll help with hiring.", ["Hiring"]),
    ("Present to the leadership team", []),
    ("Python or R for analysis", ["Python", "R"]),
    ("HR team", []),
])
def test_skill_matching_handles_ambiguous_words(text, expected):
    assert names(text) == expected


def test_a_bullet_item_is_never_a_header():
    lines = P.split_lines("Requirements:\n* Experience with dbt\n* Strong SQL\n"
                          "It's a plus if you have:\n* Experience with Looker")
    assert [ln.text for ln in lines] == ["Experience with dbt", "Strong SQL",
                                         "Experience with Looker"]
    assert [ln.section for ln in lines] == [P.REQUIREMENTS, P.REQUIREMENTS, P.PREFERRED]


def test_a_preference_mid_sentence_splits_the_line():
    lines = P.split_lines("You have 5+ years of product management experience, ideally with "
                          "developer tools.")
    tiers = [P.line_tier(ln, structured=False) for ln in lines]
    assert tiers == ["must", "nice"]


@pytest.mark.parametrize("title, years, level", [
    ("Senior Backend Engineer", 5, "Senior"),
    ("Senior Product Manager", 5, "Senior"),
    ("Product Manager", 3, "Mid-level"),
    ("Engineering Manager", 8, "Manager"),
    ("Software Engineer II", None, "Mid-level"),
    ("Staff Engineer", None, "Staff/Principal"),
    ("Data Analyst", 1, "Junior"),
    ("Lead Generation Specialist", 3, "Mid-level"),
])
def test_seniority(title, years, level):
    assert P.find_seniority(title, years) == level


def test_past_tense_handles_lists_of_verbs_and_lead_ins():
    assert to_past_tense("Design, build, and maintain scalable APIs")[0] == \
        "Designed, built, and maintained scalable APIs"
    assert to_past_tense("You will work closely with product")[0] == \
        "Worked closely with product"
    assert to_past_tense("Closely collaborate with data science")[0] == \
        "Collaborated closely with data science"
    assert to_past_tense("Mentor engineers and raise the bar")[0] == \
        "Mentored engineers and raised the bar"
    assert to_past_tense("Work with product and design")[0] == "Worked with product and design"
    assert to_past_tense("Strong communication skills")[1] is False


def test_bullets_keep_the_employers_numbers_and_add_none_of_their_own():
    b = make_bullet("Help us scale from 300 to 3,000 transactions per second", [])
    assert b == "Scaled from 300 to 3,000 transactions per second"


def test_bullets_without_numbers_get_example_figures():
    b = make_bullet("Improve the performance of our checkout API", [])
    assert b.startswith("Improved the performance of the checkout API, ")
    assert NUMBER.search(b) and "[" not in b


def test_bullets_name_the_tools_only_when_the_duty_names_none():
    assert make_bullet("Build internal tools", ["Go"]).startswith("Built internal tools using Go")
    assert "using" not in make_bullet("Build services in Go", ["Go"])


def test_strengthen_rewrites_weak_lines_and_leaves_lists_alone():
    assert strengthen("Responsible for maintaining CI pipelines").startswith(
        "Maintained CI pipelines, ")
    assert strengthen("Worked on SQL queries to clean data").startswith("Delivered SQL queries")
    assert strengthen("Cut costs by 30% with spot instances") == \
        "Cut costs by 30% with spot instances"
    skills_line = "Distributed Systems, Kafka, gRPC, PostgreSQL"
    assert strengthen(skills_line) == skills_line


# --- Whole blueprints on the samples -----------------------------------------------------------

@pytest.fixture(scope="module")
def backend():
    return build((SAMPLES / "senior-backend-go.txt").read_text(encoding="utf-8"))


def tier_of(bp, name):
    return next(s.tier for s in bp.skills if s.name == name)


def test_backend_role_snapshot(backend):
    r = backend.role
    assert r.seniority == "Senior"
    assert r.years_required == "5+ years"
    assert r.role_family == "Backend engineering"
    assert r.work_mode == "Remote"
    assert "Fintech & payments" in r.domains
    assert "Healthcare" not in r.domains  # "Health insurance" is a benefit, not the domain


def test_backend_tiers(backend):
    for must in ("Go", "PostgreSQL", "Kafka", "Kubernetes", "Docker", "AWS"):
        assert tier_of(backend, must) == "must", must
    for nice in ("Terraform", "PCI DSS", "SOC 2"):
        assert tier_of(backend, nice) == "nice", nice
    assert tier_of(backend, "On-call") == "implied"


def test_every_skill_quotes_the_posting(backend):
    jd = P.normalise((SAMPLES / "senior-backend-go.txt").read_text(encoding="utf-8"))
    for s in backend.skills:
        assert s.evidence in jd, s.name


def test_backend_resume_shape(backend):
    res = backend.resume
    assert res.headline.startswith("Senior Backend Engineer | Go")
    assert "5+ years of experience" in res.summary
    assert len(res.bullets) >= 8
    assert all(NUMBER.search(b.text) and "[" not in b.text for b in res.bullets)
    assert any(b.text.startswith("Designed, built and maintained") for b in res.bullets)
    assert res.projects and "Go service" in res.projects[0].description


def test_analyst_sample_reads_its_preferences():
    bp = build((SAMPLES / "data-analyst.txt").read_text(encoding="utf-8"))
    for nice in ("dbt", "Amplitude", "Mixpanel"):
        assert tier_of(bp, nice) == "nice", nice
    for must in ("SQL", "Python", "Statistics", "A/B testing"):
        assert tier_of(bp, must) == "must", must
    assert bp.role.title == "Data Analyst, Growth"
    assert bp.role.work_mode == "Hybrid"
    assert not bp.resume.certifications, "no education line in this posting"
    assert not any(s.name == "Build" for s in bp.skills)


def test_a_posting_with_no_headings_still_gets_duties():
    bp = build((SAMPLES / "product-manager.txt").read_text(encoding="utf-8"))
    assert bp.role.role_family == "Product management"
    texts = [b.text for b in bp.resume.bullets]
    assert any(t.startswith("Owned the roadmap") for t in texts)
    assert any(t.startswith("Defined success metrics, ran experiments") for t in texts)
    assert tier_of(bp, "Product management") == "must"
    assert tier_of(bp, "Enterprise customers") == "nice"
    assert any("posting has no clear Requirements section" in n for n in bp.notes)
