# Resume Blueprint

Paste a job description. Get the resume that employer wants to see.

For any posting it tells you:

- **What they must see**: every skill, tool and trait, sorted into must-haves, nice-to-haves, and things the duties imply. Each one links back to the exact line of the posting it came from.
- **What they are really screening for**: the signals a keyword list misses (ownership, pace, scale, regulated work, customer focus) and how to prove each on a resume.
- **Your ideal resume for this job, scoring 100/100 on the ATS check**: a headline, a summary, a skills section in the right order, 8 to 12 experience bullets with numbers, project ideas that would prove the must-haves, and the section order for the level. Download it as a single-column Word file or plain text.
- **ATS keywords**: the posting's exact spellings, with counts.
- **Your resume against it** (optional): upload your PDF or Word resume and get its ATS score, the exact lines that would take it to 100/100, the must-haves you are missing, and your weak lines rewritten.

Every bullet ends in a measured result with realistic example figures for the role: `cutting p95 latency by 39% at 19K requests/sec`. The page highlights each example number so you can swap in your own. Keep only the lines that are true for you; an interviewer will ask about every one.

## The ATS score

It checks what an applicant tracking system screens for, item by item:

| Check | Points |
|---|---|
| Each must-have skill | 3 (soft skills 1.5) |
| Each nice-to-have or implied skill | 1 (soft skills 0.5) |
| Each repeated posting keyword that is not a skill | 0.5 |
| The posting's job title, word for word | 4 |
| The years of experience asked for (stated, or shown by your dates) | 2 |
| A degree, when the posting asks for one | 1 |
| Standard headings: SUMMARY, SKILLS, EXPERIENCE, EDUCATION | 1 each |

An "X or Y" requirement is met by either. The score is the share of points earned, and it is 100 only when every check passes; 99.6 is not rounded up. The ideal resume is filled in until it passes every check, and the Word file is tested to still score 100 when read back. For your own resume, "Add these to reach 100/100" lists the skills line, proof bullets, keywords, headline and headings to add, and the score your resume would have with them.

## Run it

Needs Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

```bash
uv run python -m blueprint serve
```

Then open http://127.0.0.1:8000. Click a sample posting to see it work.

From the command line:

```bash
uv run python -m blueprint analyze samples/senior-backend-go.txt
```

```bash
uv run python -m blueprint analyze job.txt --resume my-resume.pdf -o blueprint.md
```

`--json` prints the full structured result; `--engine offline|claude|auto` picks the engine; `--resume-out resume.docx` (or `.txt`) also saves the 100/100 ideal resume.

## Two engines

| | Offline rules (default) | Claude (with an API key) |
|---|---|---|
| Needs | nothing | `ANTHROPIC_API_KEY` |
| Speed | instant | about a minute |
| Sends data anywhere | no | the posting, and your resume if given, to the Anthropic API |
| Writing | templates over the posting's own duties | written for the specific posting and your resume |

To use Claude, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. The page shows which engine answered. With a key set, "Best available" uses Claude and falls back to the offline engine (with a note saying why) if the call fails.

Claude's answer is checked before it is shown:

- Every skill and signal must quote the posting. A quote that is not in the posting is re-anchored to a posting line that names the skill, or dropped, and the page says how many were dropped.
- Skills the rules engine found that Claude missed are added back, so the Claude result never knows less than the offline one.
- A rewritten resume line must start from a line that is really in your resume.

Defaults: model `claude-opus-5-5`, effort `medium`, streaming with structured output, server-side refusal fallback on. Override with `BLUEPRINT_MODEL` and `BLUEPRINT_EFFORT` in `.env`.

## How the offline engine works

1. **Sections.** The posting is split into lines and sections (requirements, nice-to-haves, duties, about, benefits) from its headings. A list item is never taken for a heading, and benefits are ignored, so "health insurance" does not make the job a healthcare job.
2. **Tiers.** A skill is a must-have when a requirements line names it, a nice-to-have when a preferred line or a cue ("a plus", "ideally", "bonus") does, and implied when only the duties mention it. "5+ years of PM experience, ideally with developer tools" is split, so only the second half is a preference.
3. **Skills.** About 290 skills with the spellings postings use (`k8s`, `Postgres`, `Golang`, `A/B tests`). Ordinary English words only count with context: "Go" the language, not "go above and beyond"; "C", not "Series C". Unknown tools listed beside known ones ("Go, Temporal and ClickHouse") are picked up too.
4. **Bullets.** Each duty is turned into a past-tense resume bullet ("Design, build and maintain services in Go" becomes "Designed, built and maintained services in Go, ..."). A duty with its own numbers keeps them; any other gets a result that fits it (latency for performance work, incidents for reliability, decisions for analysis), with figures picked in a realistic range. The same posting always gets the same figures, and no two bullets end the same way.
5. **Gaps.** Must-haves no duty covers get a proof bullet of their own, and the role family (backend, data, product, design, sales and more) picks project ideas and the summary's focus.

The resume check reads letter-spaced PDF headings ("S K I L L S", "EDUC AT ION").

## Project layout

```
blueprint/
  parse.py         sections, tiers, title, seniority, years, work mode
  taxonomy.py      the skill list and matcher
  families.py      role families: focus, project ideas
  writing.py       duties into bullets, weak lines into strong ones
  offline.py       the offline engine
  llm.py           the Claude engine and its checks against the posting
  ats.py           the ATS score, the 100/100 ideal resume, the path to 100
  resume_check.py  your resume against a blueprint
  docx.py          the resume as a plain Word file
  engine.py        one entry point for both engines
  textio.py        text from PDF, Word and plain-text files
  render.py        Markdown output
  web.py           the web app
static/index.html  the page
samples/           three example postings
tests/             uv run pytest
```

## Tests

```bash
uv run pytest
```

The Claude tests run against a fake Anthropic API, so they need no key and no network. They check the request (model, streaming, structured output, refusal fallback), that a skill quoting text not in the posting is dropped, and that a failed call falls back to the offline engine.

## Limits

- The offline engine knows the skills in its list; a niche tool is only found when it sits in a list beside known ones. Claude has no such limit.
- Scanned PDFs have no text to read; paste the text instead.
- The ATS score models what keyword-based screening looks for. Real systems differ by vendor and by how each employer sets them up, so 100 here means nothing a scan looks for is missing, not a guaranteed pass. It does not measure how good a candidate you are.
- The example figures are typical for the role, not yours. Replace them before you send the resume.
