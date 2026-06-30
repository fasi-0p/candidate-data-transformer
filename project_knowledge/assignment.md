# Referral Request – Eightfold Engineering Intern Assignment

## Overview

This repository contains my submission for the **Eightfold Engineering Intern (Jul–Dec 2026) Assignment**: **Multi-Source Candidate Data Transformer**.

The project focuses on building a deterministic, explainable, and configurable data transformation pipeline that consolidates candidate information from multiple structured and unstructured sources into a single canonical candidate profile.

## Assignment Summary

### Objective

Build a transformation engine that:

- Ingests candidate data from multiple heterogeneous sources.
- Produces one canonical candidate profile.
- Normalizes data into consistent formats.
- Resolves conflicts deterministically.
- Tracks provenance and confidence for every field.
- Supports configurable output schemas without changing application code.

---

## Sources Supported

### Structured

- Recruiter CSV
- ATS JSON

### Unstructured

- Resume (PDF/DOCX)
- GitHub Profile

---

## Core Features

- Deterministic pipeline
- Canonical internal schema
- Field normalization
  - Phone → E.164
  - Dates → YYYY-MM
  - Countries → ISO-3166 Alpha-2
  - Skills → Canonical names
- Multi-source merge engine
- Provenance tracking
- Confidence scoring
- Runtime configurable output projection
- Schema validation
- Graceful degradation on invalid or missing inputs

---

## Processing Pipeline

1. Source Detection
2. Parsing & Extraction
3. Canonical Mapping
4. Normalization
5. Candidate Matching
6. Conflict Resolution
7. Confidence Assignment
8. Provenance Recording
9. Projection using Runtime Config
10. Output Validation

---

## Runtime Config Support

Supports:

- Selecting fields
- Renaming fields
- Field projection
- Per-field normalization
- Enable/disable provenance
- Enable/disable confidence
- Missing value strategy
  - null
  - omit
  - error

Example:

```json
{
  "fields": [
    {
      "path": "primary_email",
      "from": "emails[0]"
    }
  ],
  "include_confidence": true,
  "on_missing": "null"
}