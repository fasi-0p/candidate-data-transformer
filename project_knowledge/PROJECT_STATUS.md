# PROJECT STATUS
## Candidate Data Transformation Engine — What's Done & What's Left

> Companion to `PROJECT_KNOWLEDGE_BASE.md` (the *what/why*) and
> `../docs/DESIGN.md` (the *how*). This file is the **living progress tracker**.
>
> Last updated: 2026-06-30 · Tests: **68 passing** · ~2,250 LOC in `src/` ·
> Git: dedicated repo in project dir, 2 commits (`56a802d`, `9525cc1`).

---

## 1. Status at a glance

| Area | Status |
|------|--------|
| Design document | ✅ Done (`docs/DESIGN.md`) |
| Data model (provenance atom, canonical, config) | ✅ Done |
| Extractors: CSV (structured) | ✅ Done |
| Extractors: Resume PDF (unstructured) | ✅ Done |
| Extractors: GitHub profile JSON (priority 70) | ✅ Done |
| GitHub/LinkedIn URL handle parsing | ✅ Done |
| Normalization (phone/email/date/country/skill/location/link) | ✅ Done |
| Entity resolution (blocking + union-find + fuzzy + guard) | ✅ Done |
| Merge (deterministic, priority/agreement/conflict) | ✅ Done |
| Confidence scoring | ✅ Done |
| Provenance tracking | ✅ Done (carried by every value) |
| Validation (report, never throws) | ✅ Done |
| Projection (config-driven, runtime) | ✅ Done |
| CLI | ✅ Done |
| REST API (FastAPI) | ✅ Done |
| Web UI (minimal) | ✅ Done |
| Scaling benchmark | ✅ Done |
| Test suite (61 tests) | ✅ Done |
| README | ✅ Done |
| Dataset (all input types + edge cases) | ✅ Done (`dataset/`) |
| Git repo | ✅ Done (dedicated, committed) |
| **Demo video** | ⬜ Not started (manual deliverable) |
| **Push to GitHub remote** | ⬜ Not started |
| ATS JSON extractor | ⬜ Optional (sample data ready in `dataset/json_future/`) |
| Experience / Education parsing + merge | ⬜ Optional (model fields exist) |

**Conclusion:** the engine is **deliverable-complete against the KB scope**
(KB §4, §23). Everything remaining is optional polish or a manual deliverable
(the demo video).

---

## 2. What has been done (detail)

### 2.1 Architecture realized
The pipeline is a sequence of pure functions; I/O is isolated to extractors:

```
extract → normalize → resolve identity → merge → validate → project
```
Composed in `src/pipeline.py`, each stage timed into `RunStats`.

### 2.2 Data model — `src/models/`
- **`value.py`** — `TrackedValue` (the provenance-carrying atom: value +
  confidence + primary source + agreements + conflicts), `ValueSource`,
  `Conflict`, `clamp_confidence`. **This is the central design decision** — every
  canonical field is a `TrackedValue`, so provenance/confidence/conflicts travel
  *with* the value (makes 4/5 design principles structural).
- **`canonical.py`** — `CanonicalCandidate` (frozen, slots) + `Location`, `Link`,
  `ExperienceItem`, `EducationItem`. `record_confidence` is a *derived* property.
- **`config.py`** — `PipelineConfig` (source priorities, base confidences, region,
  fuzzy threshold), `ProjectionConfig`, `FieldMapping`, `MissingValuePolicy`.
- **`intermediate.py`** / **`normalized.py`** — loose extractor output and the
  typed-but-pre-merge records.
- **`stats.py`** — `RunStats` (per-stage timing accumulator; the only mutable model).

### 2.3 Extractors — `src/extractors/`
- **`base.py`** — `Extractor` ABC + `@register(...)` registry (new source = new
  class + one line).
- **`csv_extractor.py`** — streaming `csv.DictReader`; header alias map; multi-value
  cell splitting for emails/phones/skills; unknown columns ignored; bad rows skipped.
- **`resume_extractor.py`** — pdfplumber I/O separated from a **pure
  `parse_resume_text()`**; regex for emails/phones/links (incl. bare
  github/linkedin); heuristics for name/headline/location/skills-section/years;
  tolerant of corrupt/blank pages.
- **`github_extractor.py`** — `@register("github_json")` (GitHub source,
  priority 70). JSON I/O separated from a **pure `parse_github_profile()`**;
  maps name/email/location, `html_url`+`blog` → links, `top_languages` +
  pinned-repo languages → skills; tolerant of missing/malformed JSON (KB §18).
  Proves the "add a source = one class + one registration line" claim end-to-end.

### 2.4 Normalization — `src/normalizers/`
- **`fields.py`** — per-field normalizers returning `NormResult(value, ok)`:
  email (lowercase+validate), phone (E.164 via `phonenumbers`), date (`YYYY-MM`),
  country (ISO alpha-2 via `pycountry`, lru-cached), skill (alias map →
  canonical), name, years, location, link (kind inferred + **canonical URL** so
  the same link merges across sources + **github/linkedin handle parsed** from
  the path, e.g. `github.com/jane` → `jane`). Regexes compiled once; lookups
  memoized.
- **`engine.py`** — dispatches each field to its normalizer; malformed values are
  **kept and flagged**, not dropped.
- **`data/skill_aliases.json`** — alias → canonical skill map (~40 entries).

### 2.5 Entity resolution — `src/resolution/cluster.py`
- **Exact-key blocking** (email/phone) — O(n), links the strong-signal majority.
- **Fuzzy name matching only inside surname blocks** — `rapidfuzz.token_sort_ratio`
  ≥ threshold (90), bounded to small same-surname groups.
- **Union-find** (path compression + union by rank) — transitive clustering.
- **Contradiction guard** — two clusters that each already carry a strong id are
  never merged on name (stops fusing two different people who share a name).

### 2.6 Merge / confidence — `src/merger/merge.py`, `src/confidence/score.py`
- Deterministic per-field: winner = max(priority, completeness, lexicographic
  tiebreak); agreements raise confidence; conflicts recorded with a reason and
  lower it; collections union-and-dedup; all output sorted.
- Confidence is a **separate axis** from priority (KB §13 adjustments applied).

### 2.7 Validation — `src/validators/`
- Rule-based (not Pydantic, deliberately — needs warning/error severity and
  "valid with warnings, never throw"). Checks email/E.164/confidence-range/ISO
  country/`YYYY-MM`/duplicates/missing-id. Returns a `ValidationReport`.

### 2.8 Projection — `src/projection/`
- **`engine.py`** — reads the frozen canonical, builds a new dict; path mini-syntax
  (`emails[0]`, `location.country`); confidence/provenance toggles; missing-value
  policy. Never mutates canonical.
- **`loader.py`** — loads `ProjectionConfig` from YAML/JSON.

### 2.9 Interfaces
- **`src/cli.py`** — `--csv`, `--resume`, `--projection`, `--validate`, `--stats`,
  `--pretty`. Deterministic JSON output.
- **`src/api/app.py`** + **`store.py`** — thin FastAPI shell: `POST /api/run`,
  `POST /api/project` (reuses in-memory run store → proves projection purity),
  `GET /api/projections`, `GET /api/health`. Serves the UI from `/`.
- **`web/`** — minimal single-page UI (plain HTML/CSS/JS, neutral theme): Upload
  & Run, **Canonical Inspector** (expandable provenance/confidence/conflicts), and
  Projection Output.

### 2.10 Tooling & data
- **`scripts/benchmark.py`** — scaling demo; resolution ~2× per 2× N (near-linear).
- **`scripts/make_sample_resume.py`**, **`scripts/make_dataset.py`** — fixtures.
- **`dataset/`** — 10 CSVs + 9 resume PDFs + forward-looking JSON, covering all
  edge cases (see `dataset/README.md`).
- **`samples/`** — minimal canonical sample inputs + 2 projection configs.

### 2.11 Tests — `tests/` (68 passing)
`test_models`, `test_normalizers` (incl. **url handle parsing**), `test_merge`,
`test_resolution`, `test_resume_extractor`, `test_github_extractor` (pure parse,
robustness, cross-source merge), `test_validators`, `test_pipeline` (incl.
**byte-for-byte determinism** + projection immutability), `test_api`,
`test_benchmark`.

---

## 3. What needs to be done

### 3.1 Manual deliverables (not code)
- ⬜ **Demo video** (KB §23) — record a walkthrough using the web UI + dataset.
- ⬜ **Export the design doc to PDF** if a "Design PDF" artifact is required
  (KB §23 lists "Design PDF"; `docs/DESIGN.md` is the source).

### 3.2 Repo / distribution
- ⬜ **Push to a GitHub remote** (create repo, `git remote add`, `git push -u`).
- ⬜ Optional: CI workflow (GitHub Actions running `pytest`).

### 3.3 Optional feature extensions (all non-blocking)
- ✅ **GitHub JSON extractor** — done (`@register("github_json")`,
  `src/extractors/github_extractor.py`; sample `dataset/json/github_profile.json`).
- ⬜ **ATS JSON extractor** — sample data in `dataset/json_future/ats_export.json`;
  add a `@register("ats_json")` class. Registry makes this isolated (no other
  module changes) — same pattern the GitHub extractor just demonstrated.
- ⬜ **Experience / Education parsing + merge** — `ExperienceItem` /
  `EducationItem` exist in the model and the resume has the sections, but the
  resume parser does not yet structure them and `merge.py` does not merge them
  (only scalar + simple collection fields today).
- ⬜ **Expand the skill alias map** beyond the current ~40 entries.
- ✅/⬜ **LinkedIn** — live scraping is out of scope per KB §4; LinkedIn **URL
  parsing** (handle extraction + canonical dedup) is done. A LinkedIn data-export
  JSON extractor could be added the same way as GitHub if a non-scraped export is
  available.

### 3.4 Known limitations (documented, by design or minor)
- Link columns in CSV are **not** multi-split, so multiple comma-separated URLs in
  one `portfolio` cell stay as one raw value (noted in `dataset/README.md`).
- Resume field extraction is **heuristic** (regex + position rules); unusual
  layouts may miss headline/location. Core fields (name/email/phone/links/skills)
  are robust; covered by `robin_fisher_messy.pdf`.
- Fuzzy-name threshold (90) and default phone region (`IN`) are config defaults,
  tunable via `PipelineConfig`.

---

## 4. How to run (quick reference)

```bash
python -m pip install -e ".[api,dev]"          # setup
python -m pytest -q                            # 68 tests
python -m src.cli --csv dataset/csv/01_clean_candidates.csv --pretty
python -m src.cli --resume dataset/resumes/alex_morgan_complete.pdf \
    --github dataset/json/github_profile.json --stats   # cross-source merge
python -m uvicorn src.api.app:app              # UI+API at http://127.0.0.1:8000
python scripts/benchmark.py                    # scaling demo
python scripts/make_dataset.py                 # regenerate resume PDFs
```

See `README.md` for the full command list and `dataset/README.md` for
edge-case-specific demos.

---

## 5. Deliverables checklist (KB §23)

| Deliverable | Status | Location |
|-------------|--------|----------|
| Design document | ✅ | `docs/DESIGN.md` (+ PDF export pending if required) |
| Source code | ✅ | `src/` |
| README | ✅ | `README.md` |
| Tests | ✅ | `tests/` (61) |
| Demo video | ⬜ | manual |

---

## 6. Suggested next actions (priority order)

1. Decide whether a **Design PDF** is needed; if so, export `docs/DESIGN.md`.
2. **Record the demo video** using the UI + `dataset/`.
3. **Push to GitHub** (+ optional CI).
4. (Optional) Add the **ATS/GitHub JSON extractors** to literally exercise the
   "add a source = one class" extensibility claim end-to-end.
5. (Optional) **Experience/Education** structured parsing + merge.
