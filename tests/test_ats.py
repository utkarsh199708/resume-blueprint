"""Numbers in every point, a 100/100 ideal resume, and the lines that take a real resume to 100."""

import re
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blueprint.ats import ats_check, years_shown
from blueprint.docx import to_docx
from blueprint.offline import build
from blueprint.resume_check import check
from blueprint.textio import extract_text
from blueprint.web import app
from blueprint.writing import NUMBER, impact_for

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

FRONTEND = """Frontend Engineer (React)
About us: We build scheduling software for clinics.
What you'll do:
- Build accessible, fast UI components in React and TypeScript
- Improve page load performance and Core Web Vitals
- Work with design to ship new features every week
Requirements:
- 3+ years of experience with React, TypeScript and CSS
- Experience writing tests with Jest or Cypress
- Bachelor's degree in Computer Science or equivalent experience
Nice to have:
- Next.js, GraphQL
"""
MARKETING = """Growth Marketing Manager
Responsibilities:
- Plan and run paid campaigns across Google Ads and LinkedIn
- Own SEO and content strategy to grow organic traffic
- Report on pipeline and CAC to the leadership team
Requirements:
- 4+ years in B2B SaaS marketing
- Strong analytical skills with Google Analytics and HubSpot
- Excellent written communication
"""
ML = """Machine Learning Engineer
You will:
- Train and deploy recommendation models with PyTorch
- Build feature pipelines on Spark and Airflow
- Monitor models in production and run A/B tests
Qualifications:
- MS or PhD in Computer Science, Statistics or a related field
- 2+ years of Python and SQL
- Experience with AWS SageMaker or Kubernetes
"""
POSTINGS = {p.stem: p.read_text(encoding="utf-8") for p in sorted(SAMPLES.glob("*.txt"))}
POSTINGS |= {"frontend": FRONTEND, "marketing": MARKETING, "ml": ML}


@pytest.fixture(scope="module", params=sorted(POSTINGS))
def bp(request):
    return build(POSTINGS[request.param])


def test_every_point_has_a_number_and_no_placeholder(bp):
    for b in bp.resume.bullets:
        assert NUMBER.search(b.text), b.text
        assert "[" not in b.text, b.text
    assert NUMBER.search(bp.resume.summary) and "[" not in bp.resume.summary


def test_bullets_do_not_end_the_same_way(bp):
    shapes = [re.sub(r"[$\d][\d,.]*[%KMx]?", "#", b.text.rsplit(", ", 1)[-1])
              for b in bp.resume.bullets if ", " in b.text]
    assert len(shapes) == len(set(shapes)), shapes


def test_ideal_resume_scores_100(bp):
    assert bp.ats.score == 100, [i.label for i in bp.ats.failed]
    assert ats_check(bp, bp.resume_text).score == 100


def test_the_word_file_still_scores_100_when_read_back(bp):
    data = to_docx(bp.resume_text)
    assert "word/document.xml" in zipfile.ZipFile(BytesIO(data)).namelist()
    assert ats_check(bp, extract_text(data, "resume.docx")).score == 100


def test_numbers_are_the_same_every_time():
    assert build(FRONTEND).resume == build(FRONTEND).resume
    assert impact_for("Improve API latency") == impact_for("Improve API latency")


def test_a_degree_asked_for_is_on_the_ideal_resume():
    bp = build(FRONTEND)
    assert any(i.kind == "education" and i.passed for i in bp.ats.items)
    assert "Bachelor's degree" in bp.resume_text


def test_100_means_every_check_passes():
    bp = build(POSTINGS["senior-backend-go"])
    text = re.sub(r"\bKafka\b", "", bp.resume_text)
    report = ats_check(bp, text)
    assert 95 <= report.score < 100, "one missing must-have is not rounded up to 100"
    assert [i.label for i in report.failed] == ["Kafka"]


def test_years_are_read_from_dates_or_stated():
    assert years_shown(5, "Engineer, Acme | 2018 – Present")
    assert years_shown(5, "Backend engineer with 6+ years of experience")
    assert not years_shown(5, "Engineer, Acme | 2023 – 2025")


ANALYST_RESUME = """Jamie Rivera
Data Analyst

SUMMARY
Analyst who turns retail data into decisions.

EXPERIENCE
Analyst, ShopFast (2022-2025)
- Responsible for weekly sales reports in Excel for the marketing team
- Built Tableau dashboards tracking customer retention for 40 store managers

SKILLS
SQL, Excel, Tableau, Python
"""


def test_the_path_to_100_takes_a_real_resume_to_100():
    bp = build(POSTINGS["data-analyst"])
    rc = check(bp, ANALYST_RESUME)
    assert rc.score < 100
    assert rc.projected_score == 100
    where = [f.where for f in rc.to_100]
    assert "Skills" in where and "Section heading" in where  # EDUCATION is missing
    bullets = [f for f in rc.to_100 if f.where == "Experience bullet"]
    assert all(NUMBER.search(f.text) for f in bullets)
    # Ways of working are listed under Skills, not given a made-up "Used X to..." bullet.
    assert not any(f.text.startswith("Used stakeholder management") for f in bullets)


def test_a_perfect_resume_needs_no_fixes():
    bp = build(POSTINGS["senior-backend-go"])
    rc = check(bp, bp.resume_text)
    assert rc.score == 100 and rc.to_100 == []


def test_docx_endpoint():
    bp = build(POSTINGS["product-manager"])
    r = TestClient(app).post("/api/docx", data={"text": bp.resume_text, "filename": "pm resume"})
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
    assert 'filename="pm-resume.docx"' in r.headers["content-disposition"]
    assert TestClient(app).post("/api/docx", data={"text": " "}).status_code == 400
