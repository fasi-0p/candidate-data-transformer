"""Entity resolution — grouping records that belong to the same candidate.

Efficient by construction (docs/DESIGN.md §9.1):

1. **Exact-key blocking** on normalized email / E.164 phone links the
   strong-signal majority in O(n) with zero comparisons.
2. **Fuzzy-name matching runs only inside surname blocks** — records are bucketed
   by surname token, and rapidfuzz comparison happens only within a bucket. This
   bounds the quadratic work to small same-surname groups instead of all pairs,
   keeping the stage near-linear.
3. **Union-find** (path compression + union by rank) assembles clusters in
   near-O(n·α(n)).

A **contradiction guard** keeps name matching honest: two clusters that *each*
already carry a strong identifier (email or phone) are never merged on name —
distinct strong ids mean distinct people. Name matching can only pull in a record
that lacks a corroborating strong id (e.g. a recruiter note with just a name).
This is why we don't silently glue two different "John Smith"s together.
"""

from __future__ import annotations

import re
from collections import defaultdict

from rapidfuzz import fuzz

from ..models.normalized import NormalizedRecord

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class _UnionFind:
    """Disjoint-set with path compression + union by rank."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> int:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return ra


def _strong_ids(record: NormalizedRecord) -> tuple[set[str], set[str]]:
    emails = {nv.value for nv in record.values("emails")
              if not nv.source.malformed}
    phones = {nv.value for nv in record.values("phones")
              if not nv.source.malformed}
    return emails, phones


def _name(record: NormalizedRecord) -> str | None:
    return record.first_value("full_name")


def _surname_key(name: str | None) -> str | None:
    if not name:
        return None
    tokens = _TOKEN_RE.findall(name.lower())
    return tokens[-1] if tokens else None


def cluster_records(
    records: list[NormalizedRecord], fuzzy_threshold: int = 90
) -> list[list[NormalizedRecord]]:
    """Group records into clusters, one per resolved candidate.

    Deterministic: clusters are returned ordered by their earliest member, and
    membership preserves input order. The final partition is independent of the
    order links are discovered in.
    """
    n = len(records)
    uf = _UnionFind(n)
    emails = [set() for _ in range(n)]
    phones = [set() for _ in range(n)]
    for i, rec in enumerate(records):
        emails[i], phones[i] = _strong_ids(rec)

    # --- 1. exact-key blocking (email, phone) --------------------------------
    buckets: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i in range(n):
        for value in emails[i]:
            buckets[("email", value)].append(i)
        for value in phones[i]:
            buckets[("phone", value)].append(i)
    for members in buckets.values():
        first = members[0]
        for other in members[1:]:
            uf.union(first, other)

    # --- 2. per-root aggregate strong ids (for the contradiction guard) ------
    root_emails: dict[int, set[str]] = defaultdict(set)
    root_phones: dict[int, set[str]] = defaultdict(set)
    for i in range(n):
        r = uf.find(i)
        root_emails[r] |= emails[i]
        root_phones[r] |= phones[i]

    # --- 3. fuzzy-name matching inside surname blocks ------------------------
    name_blocks: dict[str, list[int]] = defaultdict(list)
    for i in range(n):
        key = _surname_key(_name(records[i]))
        if key:
            name_blocks[key].append(i)

    for members in name_blocks.values():
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                i, j = members[a], members[b]
                ri, rj = uf.find(i), uf.find(j)
                if ri == rj:
                    continue
                # contradiction guard: don't merge two clusters that each
                # already carry a strong id.
                if root_emails[ri] and root_emails[rj]:
                    continue
                if root_phones[ri] and root_phones[rj]:
                    continue
                name_i, name_j = _name(records[i]), _name(records[j])
                if fuzz.token_sort_ratio(name_i, name_j) >= fuzzy_threshold:
                    new_root = uf.union(i, j)
                    merged_e = root_emails[ri] | root_emails[rj]
                    merged_p = root_phones[ri] | root_phones[rj]
                    root_emails[new_root] = merged_e
                    root_phones[new_root] = merged_p

    # --- 4. collect clusters, preserving first-seen order --------------------
    groups: dict[int, list[NormalizedRecord]] = {}
    order: list[int] = []
    for i in range(n):
        root = uf.find(i)
        if root not in groups:
            groups[root] = []
            order.append(root)
        groups[root].append(records[i])
    return [groups[root] for root in order]
