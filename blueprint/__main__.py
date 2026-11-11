"""Command line.

    python -m blueprint serve [--port 8000]
    python -m blueprint analyze JOB.txt [--resume RESUME.pdf] [--engine auto|offline|claude]
                                        [--json] [-o OUT.md] [--resume-out RESUME.docx]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .docx import to_docx
from .engine import ENGINES, InputError, analyze, load_dotenv
from .render import to_markdown
from .textio import UnreadableFile, extract_text


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return extract_text(Path(path).read_bytes(), path)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="python -m blueprint",
                                 description="Job description in, resume blueprint out.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the web app")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)

    a = sub.add_parser("analyze", help="print a blueprint for one job description")
    a.add_argument("job", help="job description file (.txt, .pdf, .docx), or - for stdin")
    a.add_argument("--resume", help="your resume (.pdf, .docx, .txt) to check against it")
    a.add_argument("--engine", choices=ENGINES, default="auto")
    a.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    a.add_argument("-o", "--out", help="write to this file instead of the terminal")
    a.add_argument("--resume-out", metavar="FILE",
                   help="also save the ideal resume (scores 100/100) as .docx or .txt")

    args = ap.parse_args(argv)
    if args.cmd == "serve":
        from .web import serve

        print(f"Resume Blueprint on http://{args.host}:{args.port}")
        serve(args.host, args.port)
        return 0

    try:
        jd = _read(args.job)
        resume = _read(args.resume) if args.resume else None
        bp = analyze(jd, resume, args.engine)
    except (InputError, UnreadableFile, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.resume_out:
        target = Path(args.resume_out)
        if target.suffix.lower() == ".docx":
            target.write_bytes(to_docx(bp.resume_text))
        else:
            target.write_text(bp.resume_text, encoding="utf-8")
        print(f"Wrote {target} (ATS score {bp.ats.score}/100)", file=sys.stderr)
    out = bp.model_dump_json(indent=2) if args.json else to_markdown(bp)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
