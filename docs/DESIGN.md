# Design Document — Candidate Data Transformation Engine

> Companion to `project_knowledge/PROJECT_KNOWLEDGE_BASE.md`.
> The knowledge base says *what* to build and *why*. This document fixes the
> *how*: concrete contracts, algorithms, data shapes, and the API the web UI
> consumes. Where the knowledge base is silent or ambiguous, the decision is
> made here and the rationale recorded so it is defensible in an interview.

**Build profile:** portfolio / interview piece. Optimize for a *defensible*
architecture and clear talking points over feature breadth.

---

## 0. Design goals, restated as testable invariants

The five principles (KB §3) are only useful if they are enforceable. Each maps
to a concrete invariant we can test:

| Principle | Invariant | How it is enforced |
|-----------|-----------|--------------------|
| Never invent | No field is populated without a source | Every value is a `TrackedValue` carrying its source; "unknown" is a real, representable state |
| Explainable | Every output value traces to ≥1 source + method | Provenance is carried *by* the value, not in a side table |
| Canonical immutable | Projection cannot mutate canonical data | Projection takes a frozen canonical object, returns a new dict |
| Deterministic | `pipeline(x) == pipeline(x)` byte-for-byte | Stable sorting everywhere + a test that runs twice and diffs |
| One responsibility | Each stage is `f(in) -> out`, no hidden state | Pure functions; I/O isolated to extractors |

If a design choice makes one of these harder to test, it is the wrong choice.

---

## 1. The central decision: the `TrackedValue` atom

Everything in this system flows from one decision — **how a single field value
is represented.**

The naive reading of KB §9 + §14 is "a canonical object, plus a separate
`provenance` dictionary keyed by field name." That is the trap. Two parallel
structures (the values and their provenance) drift out of sync the moment merge
logic gets non-trivial, and it makes the immutability and determinism guarantees
manual chores instead of structural facts.

Instead, **the tracked value is the atom**, and the canonical candidate is a
tree of tracked values:

```python
@dataclass(frozen=True)
class ValueSource:
    source: str        # "Resume", "ATS", "CSV", "GitHub"
    method: str        # "exact", "regex", "fuzzy_name", "csv_column", ...
    raw: str | None    # the pre-normalization value, for auditability

@dataclass(frozen=True)
class TrackedValue(Generic[T]):
    value: T                      # normalized, canonical value
    confidence: float             # 0.0 .. 1.0
    primary: ValueSource          # the source that won
    agreements: list[ValueSource] # other sources that agreed (raised conf)
    conflicts: list[Conflict]     # losing values + why they lost

@dataclass(frozen=True)
class Conflict:
    value: Any
    source: ValueSource
    reason: str        # "lower_source_priority", "less_complete", ...
```

Consequences (all good):

- **Provenance is free.** It is already attached to every value.
- **Confidence is free.** It rides along and is adjusted in place during merge.
- **Immutability is structural.** `frozen=True` means projection *cannot*
  mutate canonical data even by accident.
- **Determinism is local.** Sorting `agreements`/`conflicts` by a stable key is
  the only discipline needed.

> **Interview line:** "I made the provenance-carrying value the fundamental unit
> instead of bolting provenance on at the end. That turned four of the five
> design principles from manual effort into structural guarantees."

---

## 2. Canonical model

```python
@dataclass(frozen=True)
class CanonicalCandidate:
    candidate_id: str                       # deterministic hash (see §5)
    full_name:        TrackedValue[str] | None
    emails:           list[TrackedValue[str]]
    phones:           list[TrackedValue[str]]      # E.164
    location:         TrackedValue[Location] | None
    links:            list[TrackedValue[Link]]
    headline:         TrackedValue[str] | None
    years_experience: TrackedValue[float] | None
    skills:           list[TrackedValue[str]]      # canonical skill names
    experience:       list[TrackedValue[ExperienceItem]]
    education:        list[TrackedValue[EducationItem]]
    # confidence + provenance are NOT separate fields — they live in each
    # TrackedValue. A top-level `record_confidence` is *derived*, not stored.
```

Scalar fields (`full_name`, `headline`, …) hold a single `TrackedValue` because
they have exactly one canonical answer. Collection fields (`emails`, `skills`, …)
hold a *list* of tracked values because a candidate legitimately has several,
and each element keeps its own provenance and confidence.

Notice what is **absent**: there is no separate `confidence` or `provenance`
field as KB §9 lists them. That listing describes the *information* that must
exist, not its physical layout. We satisfy it better by distributing it.

---

## 3. Pipeline stages and their contracts

Each stage is a pure function. Types are the contract.

```
RawSource ──[extract]──▶ list[IntermediateRecord]
                              │
                     [normalize] (per record, field by field)
                              │
                              ▼
                     list[NormalizedRecord]
                              │
                  [resolve identity]  → groups records by candidate
                              │
                              ▼
              dict[candidate_id, list[NormalizedRecord]]
                              │
                          [merge]  (one group → one canonical)
                              │
                              ▼
                     list[CanonicalCandidate]
                              │
              ┌───────────────┴───────────────┐
         [validate]                       [project]
         → ValidationReport               → output dict (per config)
```

### Stage 1–2: Extraction
- **Input:** a file path + declared source type (`csv`, `resume_pdf`, `ats_json`, `github_json`).
- **Output:** `list[IntermediateRecord]` — loosely typed, raw strings, one per
  logical candidate found in that source.
- **Rule:** extraction *never* normalizes and *never* fails the pipeline. A
  corrupt PDF returns a partial record or an empty list, never an exception that
  escapes (KB §18). Each extractor is a class registered in a registry so a new
  source is "new class + one line" (KB §22).

### Stage 3: Normalization
- Pure per-field transforms, each independently testable and toggleable:
  - email → lowercased, trimmed, dedup
  - phone → E.164 via `phonenumbers` (needs a default region; see §7 open items)
  - date → `YYYY-MM` via `dateutil`
  - country → ISO-3166 alpha-2 via `pycountry`
  - skill → canonical name via an alias map (data file, not code)
- A normalizer that *cannot* parse its input returns the original raw value
  flagged `malformed` (drives the −0.20 confidence adjustment, KB §13), rather
  than dropping it. We record that we couldn't normalize, not silence.

### Stage 4: Entity resolution  *(the part the KB undersells)*
KB §4 gives "Email → Phone → Fuzzy name." That is the *signal priority*, not the
*algorithm*. The algorithm is **clustering by union-find**:

1. **Exact-key blocking (O(n)):** bucket records by normalized email and E.164
   phone; everything in a bucket is linked with no comparison.
2. **Fuzzy name only inside surname blocks:** bucket by surname token and run
   `rapidfuzz.token_sort_ratio >= 90` (configurable) *only within a bucket*, so
   the quadratic work is bounded to small same-surname groups (docs §9.1).
3. **Union-find** collapses links into clusters — handles **transitive matches**
   correctly (A≡B by email, B≡C by phone ⇒ A,B,C one candidate).
4. **Contradiction guard** (implemented instead of a blanket name-only confidence
   penalty): two clusters that *each* already carry a strong id (email or phone)
   are never merged on name — distinct strong ids mean distinct people. Name
   matching can only absorb a record that *lacks* a corroborating strong id (e.g.
   a recruiter note with just a name). This is what actually stops two different
   "John Smith"s with different emails from being glued together.

> **Interview line:** "Identity is transitive, so I resolve it with union-find,
> not pairwise rules. Fuzzy name matching is gated two ways: it only runs inside
> surname blocks (so it stays near-linear), and a contradiction guard forbids
> merging two records that each already have a distinct email or phone — that's
> the difference between linking a name-only recruiter note and silently fusing
> two different people who happen to share a name."

### Stage 5: Merge — see §4.
### Stage 6: Confidence — see §5.
### Stage 7: Validation
- **Rule-based, report-producing** (not Pydantic): checks email format, E.164
  phone, `0 ≤ confidence ≤ 1`, ISO-3166 country, `YYYY-MM` dates, duplicate
  collection values, and presence of an id.
- Produces a **`ValidationReport`** (list of issues, each with ERROR/WARNING
  severity), it does **not** throw — a record can be "valid with warnings"
  (`is_valid` == no errors). Malformed-but-kept values surface as warnings.
- *Why not Pydantic here:* it aborts on the first error and has no warning vs.
  error severity, which fights the "valid with warnings, never throw" semantics.
  Explicit rules give per-issue severity, deterministic ordering, and
  provenance-aware messages.

### Stage 8: Projection — see §6.

---

## 4. Merge policy: priority and confidence are *different axes*

The KB conflates two things that must stay separate:

- **Priority** decides *who wins* a conflict. (KB §11)
- **Confidence** describes *how sure we are* of the winner. (KB §13)

A high-priority source can yield a low-confidence value (e.g. a resume field that
extracted malformed). Collapsing these would mean "the resume said so" forces
high confidence even when the extraction was garbage. Keep them orthogonal.

**Per-field merge algorithm** (scalar fields):

```
inputs = all TrackedValues for this field across the candidate's records
1. winner = max(inputs, key = (source_priority, completeness, stable_tiebreak))
   - source_priority: Resume 90, ATS 85, CSV 80, GitHub 70   (KB §11)
   - completeness:    longer / more-fields-populated value
   - stable_tiebreak: lexicographic on the raw value  → never random (KB §11)
2. agreements = inputs whose normalized value == winner.value (excluding winner)
3. conflicts  = inputs whose normalized value != winner.value, each tagged with
                why it lost
4. confidence = clamp(
       base[winner.source]
       + 0.05 * (len(agreements) > 0)      # agreement bonus (KB §13)
       - 0.10 * (len(conflicts)  > 0)      # conflict penalty
       - 0.20 * winner.malformed,          # bad extraction penalty
       0.0, 1.0)
```

For **collection fields** (emails, skills, …) merge is a union-with-dedup: keep
every distinct normalized value, and each surviving element carries the union of
the sources that supplied it (a skill from Resume+GitHub lists both — matches the
KB §9 skill example).

---

## 5. Confidence & `candidate_id`

**Confidence** is computed *only* inside merge (§4) and stored per-field. The
record-level confidence shown in the UI is **derived** (e.g. mean of field
confidences), never a stored, mutable number — that keeps it honest.

**`candidate_id` must be deterministic** (KB §3 determinism). It is a hash of the
strongest stable identifier available, in order: first normalized email, else
first E.164 phone, else `slug(full_name)+location`. Same inputs ⇒ same id ⇒
reproducible outputs and safe re-runs.

---

## 6. Projection engine — the extensibility showpiece

This is what graders/interviewers will poke at, so it is **config-driven, not
code-driven.** A projection is a declarative document interpreted at runtime;
adding a new output format requires **zero engine changes** (delivers KB §22).

```yaml
# projection.example.yaml
name: "ATS Export v1"
fields:
  - canonical: full_name      ->  out: candidateName
  - canonical: emails[0]      ->  out: primaryEmail
  - canonical: skills         ->  out: skillSet        # list
  - canonical: years_experience -> out: yoe
include_confidence: true        # attach per-field confidence to output?
include_provenance: false       # attach source/method?
missing_value_policy: omit       # one of: omit | null | empty_string
```

Contract: `project(canonical: CanonicalCandidate, config: ProjectionConfig) -> dict`.
It **reads** the frozen canonical object and **builds a new dict**. It never
writes back (KB §3, §15). Field selection, rename, omission, confidence toggle,
and missing-value policy are all data, not branches in code.

> **Interview line:** "Output schemas are configuration, not code. A new
> downstream consumer ships a YAML file; the engine never recompiles."

---

## 7. Architecture: pure core, thin web shell

The build is a **web UI over a deterministic library** — and the UI's purpose is
to *render the engine's explainability*, which is exactly why a UI is justified
here despite KB §1's "never flashy UI." It is not decoration; it is the
provenance/confidence/conflict viewer.

```
data_transformer/
  src/
    extractors/      csv, resume_pdf, ats_json, github_json  (+ registry)
    normalizers/     email, phone, date, country, skill      (+ alias data)
    resolution/      union-find clustering
    merger/          per-field + collection merge
    confidence/      scoring (called by merger)
    projection/      config loader + projector
    validators/      pydantic schemas + report builder
    models/          TrackedValue, CanonicalCandidate, configs
    pipeline.py      composes the stages: one pure function
    api/             FastAPI: thin adapter over pipeline.py
  web/               React/Next front end (see §8)
  tests/
  samples/           sample CSV / resume PDF / ATS / github fixtures
  docs/              this file + the design PDF export
```

**Boundary rule:** FastAPI and React know *nothing* about merge logic. They call
`pipeline.run(sources, projection_config)` and render the result. The pipeline
has no idea a web server exists. This is what makes the core unit-testable
without HTTP and keeps determinism provable.

**Open items to decide before coding** (flagged, not silently assumed):
- Default phone region for E.164 (KB examples imply India `+91`). Make it a
  config value, default `IN`.
- Fuzzy-name threshold (default 90) — expose it so it is tunable and defensible.
- Skill alias map seed list — start small (ML/AI/web stacks), data-file driven.

---

## 8. Web UI — deliberately minimal

**Scope decision:** the frontend is intentionally small. The backend is the
substance of this project; the UI exists only to make the engine's output
*legible* in a demo, and is not where engineering effort goes. A minimal,
monochrome/neutral-themed single page is sufficient. No animations, no design
system, no state-management library — plain React (or even a single static page
hitting the API) is enough.

**One page, three stacked panels:**

1. **Upload & Run** — file inputs for CSV + resume PDF (+ optional ATS/GitHub
   JSON), a projection-config selector, a Run button. No staged animation; just
   a spinner and a result.
2. **Canonical Inspector** — the merged candidate as a collapsible tree. Each
   field expands to show chosen value, confidence, winning source, agreements,
   and the conflicts that lost (with reasons). This is the only view that
   *matters* — it makes "explainable" tangible — so it gets what little UI
   polish there is.
3. **Projection Output** — pick/edit a projection config, see the output JSON
   regenerate via a separate call, with the canonical model visibly unchanged.

Styling budget: a single CSS file, system font, neutral palette. If time is
short, panels 1 and 2 alone satisfy the demo; panel 3 can be a raw JSON dump.

API surface (thin — the real work is all server-side):
```
POST /api/run        { sources[], projection_config }   -> { canonical, validation, timings }
POST /api/project    { canonical, projection_config }    -> { output }
GET  /api/projections                                    -> list of saved configs
```
`/api/project` is separate from `/api/run` precisely so output can be
re-projected without re-running the pipeline — proving projection is pure and
canonical data is frozen. `timings` exposes per-stage durations (see §9) so the
demo can *show* the backend's efficiency rather than just claim it.

---

## 9. Backend efficiency & performance — the real focus

The frontend is minimal; this is where the engineering goes. Efficiency here is
not premature micro-optimization — it is choosing algorithms and data layouts
that keep the pipeline **near-linear** and the determinism guarantee cheap.

### 9.1 The one that actually matters: avoid O(n²) entity resolution
Naive entity resolution compares every record against every other record, and
fuzzy name comparison makes each comparison itself O(L) — so the whole stage is
**O(n²·L)**, which is the only part of this pipeline that blows up on real data.
Fix it with **blocking** before any pairwise work:

1. **Exact-key blocking (hash buckets, O(n)).** Index records by normalized
   email and by E.164 phone. Records sharing an exact key are linked immediately
   with no comparison — this catches the strong-signal majority for free.
2. **Fuzzy only inside blocks.** Restrict fuzzy name comparison to records that
   share a *blocking key* (e.g. same last-name token, or same email domain).
   This collapses the O(n²) name comparison to O(n·b) where `b` is the (small)
   block size, instead of comparing every name to every other name.
3. **Union-find with path compression + union by rank** turns cluster assembly
   into near-O(n·α(n)) ≈ O(n).

Net: entity resolution goes from O(n²·L) to ~O(n) for the exact-match majority
plus bounded fuzzy work inside small blocks.

> **Interview line:** "The naive version is O(n²) on fuzzy name matching. I block
> on exact keys first so most records cluster in linear time, and only run fuzzy
> comparison inside small candidate blocks — that's the difference between this
> scaling to thousands of records and choking on hundreds."

### 9.2 Streaming, not slurping
Extractors are **generators**, not list-builders. CSV is read row-by-row
(`csv.reader` over a file handle, never `read()` then split); PDF text is
extracted page-by-page. Memory stays O(active records), not O(file size), so a
large recruiter CSV never has to fit in RAM at once.

### 9.3 Normalize once, look up in O(1)
- Skill alias map is a **dict** loaded once → O(1) canonicalization, not a scan.
- Regexes (email, phone fragments, date patterns) are **module-level compiled
  constants**, not recompiled per call.
- `pycountry` / `phonenumbers` results are wrapped in an **`@lru_cache`** so
  repeated country/region lookups are memoized.
- Each field is normalized exactly once, at the normalization stage; downstream
  stages consume normalized values and never re-parse.

### 9.4 Memory & immutability are cheap together
- Models are `frozen=True` dataclasses with **`slots=True`** — lower per-object
  memory and faster attribute access, and the freezing is what gives us
  immutability for free (§0). Efficiency and correctness point the same way.
- Sorting for determinism happens **once**, at output projection, on already-
  small per-candidate collections — not repeatedly mid-pipeline.

### 9.5 Make efficiency observable, not just asserted
The pipeline records **per-stage wall-clock timings** and counts (records in,
clusters out, conflicts found) into a `RunStats` object returned alongside the
result. This is what `/api/run`'s `timings` surfaces. A portfolio piece that can
*show* "resolution: 12ms for 5k records, linear scaling" beats one that claims it.

### 9.6 Deliberately NOT doing (and why)
- **No async/parallelism in the core.** The pipeline is pure and CPU-light after
  blocking; threading would add nondeterminism risk (§0) for negligible gain.
  Parallelism, if ever needed, belongs at the *extractor* I/O boundary only.
- **No caching layer / DB.** Out of scope (KB §4) and would undermine the
  "same inputs = same outputs from scratch" determinism story.
- **No premature SIMD/Cython.** The algorithmic win (§9.1) dominates; native
  code optimization is unjustified at this scale.

---

## 10. Testing strategy (portfolio-grade)

- **Unit:** each normalizer, the merge tie-break ordering, confidence clamping
  edge cases (0 and 1 bounds), union-find transitivity.
- **Golden / determinism:** run the full pipeline on `samples/` twice; assert the
  output JSON is byte-identical (the determinism invariant, §0).
- **Conflict fixtures:** a sample set engineered so CSV and Resume disagree on
  email — assert the higher-priority source wins, the loser is recorded in
  `conflicts`, and confidence drops by exactly 0.10.
- **Robustness:** corrupt PDF and empty CSV fixtures — assert partial/empty
  output, never an exception (KB §18, §19).
- **Projection:** same canonical object + three different configs ⇒ three
  outputs; assert the canonical object is unchanged after all three (immutability).

---

## 11. Build order (vertical slices)

Backend-weighted: steps 1–9 are the engine; the UI is a single thin step near
the end.

1. `models/` — `TrackedValue`, `CanonicalCandidate`, config types. *(Everything
   depends on these.)*
2. CSV extractor (streaming) → normalizers → trivial single-source merge →
   projection → JSON. *First end-to-end vertical slice; proves the spine.*
3. Resume PDF extractor — now there are two sources.
4. Entity resolution with **blocking + union-find** (§9.1) — now merge is real
   *and* scalable from the start, not retrofitted.
5. Confidence + conflict recording.
6. Validation report.
7. `RunStats` per-stage timings/counts (§9.5) + a small benchmark over a
   generated N-record dataset to demonstrate near-linear scaling.
8. FastAPI adapter (thin) exposing `/api/run`, `/api/project`.
9. Determinism + conflict + robustness + scaling test suites.
10. Minimal UI (single page; Inspector panel first — it is the differentiator).

Rationale for "models first": the `TrackedValue` shape is the contract every
later stage signs. Get it wrong and every stage reworks; get it right and the
rest is mechanical. Efficiency (blocking, streaming) is built in at step 2–4,
not bolted on — retrofitting algorithmic complexity is the expensive kind.

---

## 12. Interview talking points (mapped to decisions)

- *Why a TrackedValue atom?* → turns 4/5 principles into structural guarantees (§1).
- *Why union-find for identity?* → identity is transitive; pairwise rules fail (§3).
- *Why split priority from confidence?* → "who wins" ≠ "how sure"; conflating
  them launders bad extractions into false certainty (§4).
- *Why config-driven projection?* → new output formats with zero code change;
  literal proof of the extensibility claim (§6).
- *Why blocking before fuzzy matching?* → entity resolution is the only O(n²)
  stage; blocking on exact keys makes the majority linear and bounds fuzzy work
  to small candidate blocks — the difference between scaling and choking (§9.1).
- *Why streaming extractors + compiled/cached lookups?* → memory stays O(active
  records) and per-field work is done once in O(1); efficiency without
  sacrificing determinism (§9.2–9.4).
- *Why a minimal UI?* → the backend is the work; the UI only renders
  explainability and per-stage timings, so it stays a single thin page (§8).
- *Why deterministic ids + stable sort?* → reproducible, re-runnable, diffable
  output; the foundation of trust (§5, §9).

---

*End of design document.*
