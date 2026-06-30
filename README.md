# Candidate Data Transformation Engine

Ingests candidate data from heterogeneous sources (recruiter CSVs, resume PDFs),
resolves them into **one canonical profile per candidate**, and projects that
profile into any output schema defined at runtime — while recording **provenance,
confidence, and conflict history for every field**.

The engine optimizes for **correctness, explainability, determinism, and
extensibility** — not for a flashy UI. Same inputs always produce the same
output, and every output value can be traced back to the source it came from.

> Full engineering rationale and design decisions live in
> [`docs/DESIGN.md`](docs/DESIGN.md). This README is the quickstart.

---

## What it does

```
   CSV ─┐
        ├─▶ extract ─▶ normalize ─▶ resolve identity ─▶ merge ─▶ validate ─▶ project ─▶ output
Resume ─┘                (E.164,        (blocking +       (priority +   (report)   (config-
        PDF               ISO, skills,    union-find +      provenance +            driven)
                          dates)          fuzzy name)       confidence)
```

- **Normalization** — phones to E.164, countries to ISO-3166 alpha-2, dates to
  `YYYY-MM`, skills to canonical names, emails lowercased/deduped.
- **Entity resolution** — exact email/phone **blocking** links the majority in
  linear time; **fuzzy name** matching runs only inside surname blocks; a
  **contradiction guard** refuses to merge two records that each already carry a
  distinct strong id (so two different "John Smith"s stay separate).
- **Merge** — deterministic per-field resolution: priority decides the winner,
  agreements raise confidence, conflicts are recorded with a reason and lower it.
- **Provenance & confidence** — carried *by* every value, not in a side table.
- **Validation** — produces a report of errors/warnings; never throws.
- **Projection** — output schema is a YAML/JSON config interpreted at runtime;
  a new output format needs zero code changes.

---

## Quickstart

Requires **Python 3.11+**.

```bash
# install (editable, with API + dev extras)
python -m pip install -e ".[api,dev]"
```

### CLI

```bash
# canonical output (full provenance) for a CSV
python -m src.cli --csv samples/candidates.csv --pretty

# add a resume PDF; Jane's CSV row and resume merge into one candidate
python -m src.cli --csv samples/candidates.csv --resume samples/resume_jane.pdf --pretty

# project into a runtime-defined schema, and print validation + stage timings
python -m src.cli --csv samples/candidates.csv \
    --projection samples/projection_ats.yaml --validate --stats
```

### Web UI + API

```bash
python -m uvicorn src.api.app:app          # then open http://127.0.0.1:8000
```

One process serves the REST API and the minimal single-page UI. Upload a CSV
and/or resume, expand any field in the **Canonical Inspector** to see its source,
agreements, and the conflicts that lost — then re-project live without re-running.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/run` | multipart upload → `{ run_id, candidates, validation, timings }` |
| `POST /api/project` | `{ run_id, projection_id \| projection }` → projected output |
| `GET /api/projections` | available projection configs |

### Tests & benchmark

```bash
python -m pytest -q                        # 60 tests
python scripts/benchmark.py                # scaling demo (near-linear resolution)
```

The benchmark generates synthetic candidates and times each stage across growing
N; resolution scales ~2× per doubling of N (an O(n²) resolver would be ~4×).

---

## Project layout

```
src/
  models/        TrackedValue (the provenance-carrying atom), canonical model, config
  extractors/    registry + CSV (streaming) and resume-PDF extractors
  normalizers/   per-field normalizers + dispatch engine + skill alias data
  resolution/    entity resolution: blocking + union-find + fuzzy name
  merger/        deterministic per-field merge
  confidence/    confidence scoring
  validators/    rule-based validation report
  projection/    config-driven projection engine + loader
  pipeline.py    composes the stages; records per-stage timings
  cli.py         command-line entry point
  api/           thin FastAPI shell over the pipeline
web/             minimal single-page UI (plain HTML/CSS/JS)
samples/         example CSV, resume PDF, projection configs
scripts/         sample-resume generator, scaling benchmark
tests/           60 tests
docs/DESIGN.md   the engineering design document
```

## Adding a new source

The pipeline is built so a new source is **a new class plus one registration
line** — no existing module changes:

```python
from .base import Extractor, register

@register("my_source")
class MyExtractor(Extractor):
    source_label = "MySource"
    def extract(self, path): ...   # yield IntermediateRecords
```

## Design principles (enforced as tested invariants)

- **Never invent** — "unknown" is representable; nothing is populated without a source.
- **Explainable** — every value traces to its source(s) and method.
- **Canonical is immutable** — `frozen` dataclasses; projection only reads.
- **Deterministic** — stable sorting everywhere; a test runs the pipeline twice
  and asserts byte-identical output.
- **One responsibility per stage** — each stage is a pure `f(in) -> out`.

## Out of scope

Authentication, databases, OCR, distributed systems, real-time streaming,
ML-based entity resolution, and production deployment are intentionally excluded.
