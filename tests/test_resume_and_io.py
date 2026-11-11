"""Checking a resume, reading files, and the web API."""

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blueprint.offline import build
from blueprint.resume_check import check, unspace_headings
from blueprint.textio import UnreadableFile, extract_text
from blueprint.web import app

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
RESUME = """Jamie Rivera
Data Analyst

SUMMARY
Analyst who turns retail data into decisions.

EXPERIENCE
Analyst, ShopFast (2022-2025)
- Responsible for weekly sales reports in Excel for the marketing team
- Built Tableau dashboards tracking customer retention for 40 store managers
- Worked on SQL queries to clean order data
- Helped run A/B tests on the checkout page

SKILLS
SQL, Excel, Tableau, Python
"""


@pytest.fixture(scope="module")
def analyst_check():
    bp = build((SAMPLES / "data-analyst.txt").read_text(encoding="utf-8"))
    return check(bp, RESUME)


def test_resume_check_finds_gaps(analyst_check):
    rc = analyst_check
    assert 20 < rc.score < 80
    assert {"SQL", "Python", "A/B testing"} <= set(rc.matched)
    assert "Statistics" in rc.missing_must
    assert {"dbt", "Amplitude", "Mixpanel"} <= set(rc.missing_nice)


def test_one_alternative_satisfies_an_or_requirement(analyst_check):
    # "Experience with Python (pandas) or R": the resume has Python, so R is not missing.
    assert "R" not in analyst_check.missing_must


def test_weak_lines_are_rewritten_without_touching_strong_ones(analyst_check):
    rewrites = {t.original: t.rewritten for t in analyst_check.tailored_bullets}
    assert rewrites["Responsible for weekly sales reports in Excel for the marketing team"] \
        .startswith("Delivered weekly sales reports in Excel")
    assert rewrites["Helped run A/B tests on the checkout page"].startswith("Ran A/B tests")
    assert rewrites["Worked on SQL queries to clean order data"].startswith("Delivered SQL")
    assert not any(o.startswith("Built Tableau") for o in rewrites)  # it already has a number


def test_actions_are_concrete(analyst_check):
    text = " ".join(analyst_check.actions)
    assert "Statistics" in text
    assert "have no number" in text
    assert "2+ years" not in text, "the dates 2022-2025 already show the years asked for"


def test_letter_spaced_pdf_headings_are_joined():
    assert unspace_headings("T E C H N I C A L  S K I L L S") == "TECHNICAL SKILLS"
    assert unspace_headings("I built A B testing") == "I built A B testing"
    assert unspace_headings("EDUC AT ION\nB.Tech, 2019") == "EDUCATION\nB.Tech, 2019"


def make_docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def test_reads_word_files():
    text = extract_text(make_docx(["Senior Engineer", "Built APIs in Go"]), "cv.docx")
    assert text == "Senior Engineer\nBuilt APIs in Go"


def test_a_scanned_pdf_gets_a_clear_message():
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    w.write(buf)
    with pytest.raises(UnreadableFile, match="no text layer"):
        extract_text(buf.getvalue(), "scan.pdf")


def test_reads_windows_encoded_text():
    assert extract_text("Café – résumé".encode("cp1252"), "jd.txt") == "Café – résumé"


# --- Web API ----------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    return TestClient(app)


def test_page_and_status(client):
    assert "Resume Blueprint" in client.get("/").text
    assert client.get("/api/status").json()["claude"] is False
    names = [s["name"] for s in client.get("/api/samples").json()]
    assert "senior-backend-go" in names
    assert client.get("/api/samples/..%2Fpyproject").status_code == 404


def test_blueprint_from_pasted_text(client):
    jd = (SAMPLES / "senior-backend-go.txt").read_text(encoding="utf-8")
    r = client.post("/api/blueprint", data={"jd_text": jd, "resume_text": RESUME})
    assert r.status_code == 200
    body = r.json()
    assert body["blueprint"]["engine"] == "offline"
    assert body["blueprint"]["resume_check"]["score"] >= 0
    assert body["markdown"].startswith("# Resume blueprint: Senior Backend Engineer")


def test_blueprint_from_uploaded_files(client):
    jd = (SAMPLES / "data-analyst.txt").read_bytes()
    r = client.post("/api/blueprint", files={
        "jd_file": ("jd.txt", jd, "text/plain"),
        "resume_file": ("cv.docx", make_docx(RESUME.splitlines()), "application/octet-stream"),
    })
    assert r.status_code == 200
    assert r.json()["resume_chars"] > 100


def test_bad_input_is_a_400_with_a_reason(client):
    r = client.post("/api/blueprint", data={"jd_text": "too short"})
    assert r.status_code == 400 and "full job description" in r.json()["detail"]
    jd = (SAMPLES / "data-analyst.txt").read_text(encoding="utf-8")
    r = client.post("/api/blueprint", data={"jd_text": jd, "engine": "claude"})
    assert r.status_code == 400 and "ANTHROPIC_API_KEY" in r.json()["detail"]
