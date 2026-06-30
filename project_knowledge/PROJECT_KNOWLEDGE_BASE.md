
# PROJECT KNOWLEDGE BASE
## Candidate Data Transformation Engine
### Engineering Specification & Agent Knowledge Base

> **Purpose**
>
> This document is the single source of truth for implementing the assignment.
> Any engineer or coding agent should be able to build the project from this
> document alone without making architectural assumptions.

---

# 1. Executive Summary

The system ingests candidate information from multiple heterogeneous sources
(structured and unstructured), converts them into a unified canonical model,
resolves conflicting information deterministically, records provenance for every
field, computes explainable confidence scores, validates the final record and
finally projects the canonical profile into an output schema defined at runtime
through configuration.

The engine should prioritize:

- Correctness
- Explainability
- Determinism
- Extensibility
- Maintainability

Never optimize for flashy UI.

---

# 2. Business Problem

Recruiting platforms receive candidate data from:

- Recruiter CSVs
- ATS exports
- Resume PDFs
- GitHub
- LinkedIn
- Recruiter notes

Each source has:

- Missing fields
- Duplicate information
- Different naming conventions
- Conflicting values
- Different trust levels

The objective is to create **one trustworthy profile**.

---

# 3. Core Engineering Principles

## Principle 1

Never invent information.

Unknown is preferable to incorrect.

## Principle 2

Every value must be explainable.

Every output value should be traceable to its source.

## Principle 3

Canonical data is immutable.

Projection never edits canonical data.

## Principle 4

Pipeline must be deterministic.

Same inputs = same outputs.

## Principle 5

Every module has one responsibility.

---

# 4. Scope

## Required

- Support at least one structured source
- Support at least one unstructured source
- Normalize data
- Merge information
- Resolve conflicts
- Compute confidence
- Record provenance
- Configurable output
- Validation
- CLI OR minimal UI

## Out of Scope

- Authentication
- Database
- OCR
- Distributed systems
- Real-time streaming
- ML-based entity resolution
- LinkedIn scraping
- Production deployment

---

# 5. Recommended Tech Stack

Backend
- Python 3.11+

Framework
- FastAPI

Extraction
- pdfplumber
- pypdf

Validation
- Pydantic

Dates
- dateutil

Phone normalization
- phonenumbers

Country normalization
- pycountry

Fuzzy matching
- rapidfuzz

Frontend (optional)
- React / Next.js

---

# 6. High-Level Architecture

```text
             CSV
               \
Resume ----------> Extractors
                     |
                     V
             Intermediate Records
                     |
                     V
              Normalization Engine
                     |
                     V
              Entity Resolution
                     |
                     V
                Merge Engine
                     |
                     V
             Canonical Candidate
                     |
          -------------------------
         |                         |
         V                         V
 Validation Engine         Projection Engine
         |                         |
          -----------> Final JSON
```

---

# 7. Folder Structure

```text
src/
    extractors/
    normalizers/
    merger/
    confidence/
    provenance/
    projection/
    validators/
    models/
    config/
    utils/
tests/
samples/
docs/
```

---

# 8. Pipeline Stages

## Stage 1

Detect source type.

## Stage 2

Extract raw information.

Output:

Intermediate Record.

## Stage 3

Normalize

Examples

Phone

9876543210

↓

+919876543210

Dates

Jan 2024

↓

2024-01

Country

India

↓

IN

Emails

Lowercase

Skills

Canonical names

---

## Stage 4

Entity Resolution

Determine whether multiple records belong to the same candidate.

Recommended matching priority

1. Email
2. Phone
3. Fuzzy name

---

## Stage 5

Merge

Create one canonical record.

---

## Stage 6

Confidence

Assign confidence for each field.

---

## Stage 7

Validation

Schema validation.

---

## Stage 8

Projection

Transform canonical model into requested schema.

---

# 9. Canonical Candidate Model

Required fields

- candidate_id
- full_name
- emails
- phones
- location
- links
- headline
- years_experience
- skills
- experience
- education
- confidence
- provenance

Suggested Skill object

```json
{
  "name":"Python",
  "confidence":0.95,
  "sources":["Resume","GitHub"]
}
```

---

# 10. Normalization Rules

Emails

- lowercase
- remove duplicates

Phones

- E.164

Dates

- YYYY-MM

Countries

- ISO-3166 Alpha-2

Skills

Map aliases

Example

ML

Machine Learning

machine-learning

↓

Machine Learning

---

# 11. Merge Policy

Recommended source priority

Resume = 90

ATS = 85

CSV = 80

GitHub = 70

Rules

Higher priority wins.

If equal

Choose more complete value.

If still equal

Use deterministic ordering.

Never choose randomly.

---

# 12. Conflict Resolution

If sources disagree

- Preserve provenance
- Record conflict
- Select winner deterministically
- Reduce confidence

---

# 13. Confidence Model

Base confidence

Resume = 0.90

ATS = 0.85

CSV = 0.80

GitHub = 0.70

Adjustments

Agreement +0.05

Conflict -0.10

Malformed extraction -0.20

Clamp to

0 ≤ confidence ≤ 1

---

# 14. Provenance

Every field stores

- Source
- Extraction method
- Confidence

Example

```json
{
  "email":{
    "value":"john@gmail.com",
    "source":"CSV",
    "method":"Exact Match",
    "confidence":0.80
  }
}
```

---

# 15. Projection Engine

Purpose

Convert canonical model into any requested schema.

Supported

- Rename fields
- Select fields
- Omit fields
- Include confidence
- Missing value policy

Canonical model is never modified.

---

# 16. Runtime Configuration

Support

- field selection
- field rename
- normalization toggle
- confidence toggle
- missing value strategy

---

# 17. Validation Rules

Always validate

- email format
- phone format
- confidence range
- date format
- duplicate removal

---

# 18. Error Handling

Malformed PDF

Return partial profile.

Bad CSV

Skip invalid rows.

Unknown fields

Ignore.

Never crash entire pipeline because one source fails.

---

# 19. Edge Cases

- Duplicate emails
- Duplicate skills
- Multiple phones
- Missing resume
- Empty CSV
- Corrupted PDF
- Different spellings
- Empty experience
- Invalid dates

---

# 20. Testing Strategy

Unit Tests

- Normalization
- Merge
- Confidence
- Validation

Integration Tests

CSV + Resume

Projection

Conflict Resolution

---

# 21. Non-Functional Requirements

- Deterministic
- Explainable
- Modular
- Easily extensible
- Maintainable
- Fast

---

# 22. Extension Points

Adding a new source should require

1. New Extractor
2. Registration
3. Optional normalization rules

No existing modules should change.

---

# 23. Deliverables

- Design PDF
- Source Code
- README
- Tests
- Demo Video

---

# 24. Interview Talking Points

Why canonical schema?

Because every downstream consumer uses a stable model.

Why projection layer?

Allows runtime schema customization without code changes.

Why provenance?

Improves explainability and debugging.

Why deterministic merge?

Ensures reproducibility.

Why modular architecture?

Supports future source expansion with minimal changes.

---

# 25. Definition of Success

The project is successful if:

- Multiple heterogeneous inputs become one canonical profile.
- Every field is normalized.
- Conflicts are resolved deterministically.
- Confidence is explainable.
- Provenance exists.
- Output schema is configurable.
- System is modular and maintainable.

End of Knowledge Base.
