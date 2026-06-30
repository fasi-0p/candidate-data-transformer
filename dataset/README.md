# Dataset

Comprehensive sample inputs for the Candidate Data Transformation Engine,
covering every consumable source type and the edge cases from the knowledge base
(§18 error handling, §19 edge cases). Use these to demo the engine, exercise the
pipeline, and stress the normalizers / entity resolution / merge / validation.

```
dataset/
  csv/          structured CSV inputs (clean + edge cases)
  resumes/      unstructured resume PDFs (incl. corrupted/blank)
  json/         GitHub profile JSON (consumable via the github_json extractor)
  json_future/  forward-looking ATS sample (extractor not wired yet)
```

> Regenerate the PDFs any time with: `python scripts/make_dataset.py`

---

## CSV inputs (`dataset/csv/`)

| File | What it exercises |
|------|-------------------|
| `01_clean_candidates.csv` | Baseline: 5 well-formed candidates, international phones (IN/US/UK/IT/JP), schemed URLs. |
| `02_duplicates_and_multivalue.csv` | **Same candidate across rows** (entity resolution merges them); duplicate emails/skills within a cell (deduped); multiple phones (`;`-separated); case-insensitive email match; **headline conflict** between the two rows. |
| `03_spellings_and_aliases.csv` | **Skill aliases** (`ml`, `py`, `reactjs`, `k8s`, `postgres`, `golang`, `cpp`, `c#`, …) → canonical names; country variants (`India`/`IN`/`U.S.A.`/`Deutschland`/`China`); name spelling variants; alternate column headers (`mobile`, `country`, `title`, `yoe`, `skillset`). |
| `04_invalid_and_malformed.csv` | **Never crashes.** Bad emails (no `@`), invalid phones (`123`, `call-me-maybe`), non-numeric years (`five years`), empty/whitespace-heavy fields, commas/quotes in values → malformed flags + validation **errors** (run with `--validate`). |
| `05_missing_fields.csv` | Sparse rows: name-only, email-only, phone-only, headline-only. "Unknown is preferable to incorrect" — partial profiles, no fabricated data. |
| `06_unknown_columns.csv` | Unrecognized columns (`internal_id`, `salary`, `notes`, `security_clearance`) are **ignored**; valid columns still parse. |
| `07_urls_edge_cases.csv` | URL normalization: schemed / bare (`github.com/x`) / `www.` / trailing slash / uppercase host; **canonical dedup** of the same link in two formats; garbage/non-URL values; `portfolio`/`website` columns. |
| `08_header_only_empty.csv` | Header row, no data → **0 candidates**, no crash. |
| `09_completely_empty.csv` | 0-byte file → 0 candidates, no crash. |
| `10_conflicts_vs_resume.csv` | Pairs with resume PDFs below to demonstrate **cross-source merge + conflict resolution** (Jordan Blake) and **name-only fuzzy merge** (Sam Rivera). |

## Resume PDFs (`dataset/resumes/`)

| File | What it exercises |
|------|-------------------|
| `jordan_blake_match.pdf` | **Matches** `10_conflicts_vs_resume.csv` by email+phone. Resume (priority 90) wins the **headline** and **years** conflicts over the CSV; email/phone agree → confidence rises. |
| `sam_rivera_note.pdf` | **Name-only** recruiter note (no contacts). Merges with Sam Rivera in the CSV via **fuzzy name** (the contradiction guard allows it because the note has no competing strong id). |
| `alex_morgan_complete.pdf` | Full, well-structured resume: multiple emails, all URL types, aliased skills, summary with years, experience + education. |
| `robin_fisher_messy.pdf` | **Adversarial layout**: a `Contact:` line before the name, scattered emails/phones, bullet-ish skills, lowercased section headers. |
| `casey_stone_urls.pdf` | **URL-heavy**: bare `github.com`, `www.` + trailing slash, schemed LinkedIn, `http://` portfolio, blog path. |
| `dana_white_no_skills.pdf` | No `Skills` section → skills come out empty (not invented). |
| `jose_muller_unicode.pdf` | Accented/international name and location, international phone. |
| `blank_no_text.pdf` | Valid PDF with **no extractable text** → yields no record, no crash. |
| `corrupted.pdf` | Not a valid PDF → extractor returns nothing, **pipeline does not crash** (KB §18). |

## GitHub source (`dataset/json/`)

`github_profile.json` is **consumable** by the GitHub source (priority 70), wired
via `@register("github_json")`. The extractor maps `name`/`email`/`location`,
`html_url` + `blog` → links (with the **handle parsed** out of github/linkedin
URLs), and `top_languages` + pinned-repo languages → skills. It shares Alex
Morgan's email with `alex_morgan_complete.pdf`, so the two merge into one
candidate (Resume priority 90 wins conflicts; GitHub agreement raises confidence).

```bash
# GitHub profile alone
python -m src.cli --github dataset/json/github_profile.json --pretty

# Cross-source merge: resume (90) + GitHub (70) for the same person
python -m src.cli --resume dataset/resumes/alex_morgan_complete.pdf \
    --github dataset/json/github_profile.json --stats
```

## Recruiter notes (`dataset/notes/`)

`recruiter_notes.txt` is **consumable** by the notes source (priority 60), wired via
`@register("notes", "recruiter_notes")`. One `.txt` holds one or more candidates,
split by `---`/`===` rule lines (or blank lines). Each block is parsed as
**structured** `Field: value` lines first (`Name`, `Email`, `Title`, `Skills`, …);
a block with no recognizable fields falls back to **prose** heuristics (name,
emails, phones, a title-ish headline, best-effort skills). Its low trust is by
design — the point is cross-verification: a note's email/name agreeing or
conflicting with CSV/ATS/Resume moves confidence via the normal merge machinery.

```bash
# 3 candidates: two structured blocks + one prose block
python -m src.cli --notes dataset/notes/recruiter_notes.txt --pretty

# A note cross-verifies a CSV candidate (shared email -> agreement -> confidence up)
python -m src.cli --csv samples/candidates.csv --notes dataset/notes/recruiter_notes.txt
```

## LinkedIn — verification only (not a source)

LinkedIn cannot be fetched or scraped (KB §4), so it is **not a data source**.
Instead, pass a LinkedIn id (handle or URL) with `--linkedin-id` to **verify** it
against the LinkedIn handle a candidate already carries (e.g. from the resume):
a **match** adds an agreement-style confidence bonus + an `info` note; a
**mismatch** applies a penalty + a `warning`. LinkedIn URLs found inside other
sources (CSV/ATS/resume) are still canonicalized and their handle parsed as links.

```bash
python -m src.cli --csv samples/candidates.csv --linkedin-id janedoe --validate
```

## ATS source (`dataset/json/ats_export.json`)

`ats_export.json` is **consumable** by the ATS source (priority 85), wired via
`@register("ats_json", "ats")`. The extractor maps ATS camelCase keys
(`fullName`, `currentTitle`, `yearsExperience`, `email`/`phone`, `skills`),
flattens nested `location` (`{city, region, country}`) and `links`
(`{github, linkedin}`), and accepts either a `{"candidates": [...]}` blob, a bare
list, or a single object. Jordan Blake shares email+phone with
`10_conflicts_vs_resume.csv` and `jordan_blake_match.pdf`, so all three merge into
one candidate (Resume 90 > ATS 85 > CSV 80 on conflicts; agreements raise confidence).

```bash
# ATS export alone (2 candidates)
python -m src.cli --ats dataset/json/ats_export.json --pretty

# Three-source merge: CSV (80) + ATS (85) + Resume (90) for Jordan Blake
python -m src.cli --csv dataset/csv/10_conflicts_vs_resume.csv \
    --ats dataset/json/ats_export.json \
    --resume dataset/resumes/jordan_blake_match.pdf --stats
```

## Future sources (`dataset/json_future/`)

`ats_export.json` here is the original **forward-looking** copy; the ATS source is
now wired against `dataset/json/ats_export.json` (see above).

---

## Try it

```bash
# Baseline
python -m src.cli --csv dataset/csv/01_clean_candidates.csv --pretty

# Duplicates merge; emails/skills dedup; conflict recorded
python -m src.cli --csv dataset/csv/02_duplicates_and_multivalue.csv --pretty

# Skill aliases + country normalization
python -m src.cli --csv dataset/csv/03_spellings_and_aliases.csv --pretty

# Invalid input: errors reported, never crashes
python -m src.cli --csv dataset/csv/04_invalid_and_malformed.csv --validate

# Cross-source merge + conflicts + name-only fuzzy match
python -m src.cli --csv dataset/csv/10_conflicts_vs_resume.csv \
    --resume dataset/resumes/jordan_blake_match.pdf \
    --resume dataset/resumes/sam_rivera_note.pdf --stats

# Robustness: corrupted / blank PDFs -> 0 candidates, no crash
python -m src.cli --resume dataset/resumes/corrupted.pdf \
    --resume dataset/resumes/blank_no_text.pdf

# Everything at once, projected into the ATS schema
python -m src.cli --csv dataset/csv/01_clean_candidates.csv \
    --csv dataset/csv/03_spellings_and_aliases.csv \
    --resume dataset/resumes/alex_morgan_complete.pdf \
    --projection samples/projection_ats.yaml --pretty
```

Or load any of these in the web UI: `python -m uvicorn src.api.app:app` →
http://127.0.0.1:8000
