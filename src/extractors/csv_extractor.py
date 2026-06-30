"""Streaming CSV extractor.

Reads row-by-row with `csv.DictReader` over a file handle — never `read()` then
split — so memory stays O(active record), not O(file size) (docs/DESIGN.md §9.2).
Malformed rows are skipped, not fatal (KB §18).
"""

from __future__ import annotations

import csv
import re
from typing import Iterator

from ..models.intermediate import IntermediateRecord, RawField
from .base import Extractor, register

# Header (normalized) -> canonical field name.
_COLUMN_MAP: dict[str, str] = {
    "name": "full_name",
    "fullname": "full_name",
    "full_name": "full_name",
    "candidate": "full_name",
    "candidate_name": "full_name",
    "email": "emails",
    "emails": "emails",
    "email_address": "emails",
    "phone": "phones",
    "phones": "phones",
    "mobile": "phones",
    "contact": "phones",
    "location": "location",
    "city": "location",
    "country": "location",
    "headline": "headline",
    "title": "headline",
    "summary": "headline",
    "years_experience": "years_experience",
    "experience": "years_experience",
    "yoe": "years_experience",
    "years": "years_experience",
    "skills": "skills",
    "skillset": "skills",
    "github": "links",
    "linkedin": "links",
    "portfolio": "links",
    "website": "links",
}

# Fields whose cell may pack several values.
_MULTI_SPLIT = re.compile(r"[;,]")
_MULTI_FIELDS = {"emails", "phones", "skills"}


def _norm_header(header: str) -> str:
    return re.sub(r"[\s\-]+", "_", header.strip().lower())


@register("csv")
class CsvExtractor(Extractor):
    source_label = "CSV"

    def extract(self, path: str) -> Iterator[IntermediateRecord]:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header_to_field = {
                col: _COLUMN_MAP.get(_norm_header(col))
                for col in (reader.fieldnames or [])
            }
            for row in reader:
                record = self._row_to_record(row, header_to_field)
                if record.fields:  # skip wholly empty rows
                    yield record

    def _row_to_record(
        self, row: dict[str, str], header_to_field: dict[str, str | None]
    ) -> IntermediateRecord:
        record = IntermediateRecord(source=self.source_label)
        for col, field in header_to_field.items():
            if field is None:
                continue  # unknown column — ignore (KB §18)
            raw = (row.get(col) or "").strip()
            if not raw:
                continue
            self._add(record, field, raw, method="csv_column")
        return record

    @staticmethod
    def _add(
        record: IntermediateRecord, field: str, raw: str, method: str
    ) -> None:
        values = (
            [v.strip() for v in _MULTI_SPLIT.split(raw) if v.strip()]
            if field in _MULTI_FIELDS
            else [raw]
        )
        if field in {"emails", "phones", "skills", "links"}:
            bucket = record.fields.setdefault(field, [])
            assert isinstance(bucket, list)
            bucket.extend(RawField(v, method=method) for v in values)
        else:
            # scalar: last writer wins within a row (single column anyway)
            record.fields[field] = RawField(values[0], method=method)
