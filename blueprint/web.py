"""The web app: one page, one JSON endpoint."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response
from starlette.concurrency import run_in_threadpool

from . import llm
from .docx import to_docx
from .engine import ROOT, InputError, analyze, load_dotenv
from .render import to_markdown
from .textio import UnreadableFile, extract_text

load_dotenv()
STATIC = ROOT / "static"
SAMPLES = ROOT / "samples"

app = FastAPI(title="Resume Blueprint", docs_url=None, redoc_url=None)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html", media_type="text/html")


@app.get("/api/status")
def status() -> dict:
    return {"claude": llm.available(), "model": llm.configured_model()}


@app.get("/api/samples")
def samples() -> list[dict]:
    return [{"name": p.stem, "label": p.stem.replace("-", " ").title()}
            for p in sorted(SAMPLES.glob("*.txt"))]


@app.get("/api/samples/{name}", response_class=PlainTextResponse)
def sample(name: str) -> str:
    path = (SAMPLES / f"{name}.txt").resolve()
    if path.parent != SAMPLES.resolve() or not path.exists():
        raise HTTPException(404, "No such sample.")
    return path.read_text(encoding="utf-8")


async def _read(upload: UploadFile | None) -> str:
    if upload is None or not upload.filename:
        return ""
    data = await upload.read()
    if not data:
        return ""
    try:
        return extract_text(data, upload.filename)
    except UnreadableFile as exc:
        raise HTTPException(400, f"{upload.filename}: {exc}") from exc


@app.post("/api/blueprint")
async def blueprint(
    jd_text: Annotated[str, Form()] = "",
    resume_text: Annotated[str, Form()] = "",
    engine: Annotated[str, Form()] = "auto",
    jd_file: Annotated[UploadFile | None, File()] = None,
    resume_file: Annotated[UploadFile | None, File()] = None,
) -> dict:
    jd = jd_text.strip() or await _read(jd_file)
    resume = resume_text.strip() or await _read(resume_file)

    try:
        bp = await run_in_threadpool(analyze, jd, resume or None, engine)
    except InputError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"blueprint": bp.model_dump(), "markdown": to_markdown(bp),
            "resume_chars": len(resume)}


@app.post("/api/docx")
def docx(text: Annotated[str, Form()] = "",
         filename: Annotated[str, Form()] = "resume") -> Response:
    """The ideal resume (or any edited resume text) as a plain, ATS-friendly Word file."""
    if not text.strip() or len(text) > 60_000:
        raise HTTPException(400, "Nothing to put in the document.")
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-.")[:80] or "resume"
    return Response(to_docx(text), media_type=DOCX_TYPE,
                    headers={"Content-Disposition": f'attachment; filename="{name}.docx"'})


DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)
