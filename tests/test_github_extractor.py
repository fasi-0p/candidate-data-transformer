"""Tests for the GitHub JSON extractor (pure parse + cross-source merge)."""

import json
from pathlib import Path

import pytest

from src.extractors.github_extractor import parse_github_profile
from src.pipeline import Source, run

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CSV = str(SAMPLES / "candidates.csv")
GITHUB_JANE = str(SAMPLES / "github_jane.json")

PROFILE = {
    "login": "octocat",
    "name": "Octo Cat",
    "email": "octo@example.com",
    "blog": "https://octo.dev",
    "location": "Seattle, USA",
    "html_url": "https://github.com/octocat",
    "top_languages": ["Python", "Go"],
    "pinned_repos": [
        {"name": "a", "language": "Python"},   # duplicate language -> deduped
        {"name": "b", "language": "Rust"},
    ],
}


def values(rec, field):
    raw = rec.fields[field]
    items = raw if isinstance(raw, list) else [raw]
    return [x.value for x in items]


def test_parse_maps_profile_fields():
    rec = parse_github_profile(PROFILE)
    assert rec.source == "GitHub"
    assert values(rec, "full_name") == ["Octo Cat"]
    assert values(rec, "emails") == ["octo@example.com"]
    assert values(rec, "location") == ["Seattle, USA"]
    # html_url + blog both captured.
    assert set(values(rec, "links")) == {
        "https://github.com/octocat", "https://octo.dev"}
    # top_languages + pinned-repo languages, deduped.
    assert values(rec, "skills") == ["Python", "Go", "Rust"]


def test_parse_synthesizes_github_url_from_login_when_no_html_url():
    rec = parse_github_profile({"login": "ada", "name": "Ada"})
    assert values(rec, "links") == ["https://github.com/ada"]


def test_parse_invents_nothing_for_empty_profile():
    rec = parse_github_profile({})
    assert rec.fields == {}


def test_extract_tolerates_bad_file(tmp_path):
    from src.extractors.github_extractor import GithubExtractor
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    assert list(GithubExtractor().extract(str(bad))) == []
    assert list(GithubExtractor().extract(str(tmp_path / "missing.json"))) == []


def test_github_merges_with_csv_and_contributes_skills():
    # github_jane.json shares Jane's email with the CSV row -> one candidate.
    result = run([Source("csv", CSV), Source("github_json", GITHUB_JANE)])
    janes = [c for c in result.candidates if c.full_name.value == "Jane Doe"]
    assert len(janes) == 1, "GitHub profile should merge into the CSV candidate"
    jane = janes[0]

    # CSV skills (ML/Python/React) unioned with GitHub's (TypeScript/Go) + Python.
    skills = {s.value for s in jane.skills}
    assert {"TypeScript", "Go"} <= skills

    # The github link is present with a parsed handle.
    gh = next(l for l in jane.links if l.value.kind == "github")
    assert gh.value.handle == "janedoe"

    # CSV (priority 80) wins headline over GitHub (70); resolution stays linear.
    assert result.stats.clusters_out == 3


def test_github_only_run_produces_a_candidate():
    result = run([Source("github_json", GITHUB_JANE)])
    assert len(result.candidates) == 1
    c = result.candidates[0]
    assert c.full_name.value == "Jane Doe"
    assert c.full_name.primary.source == "GitHub"


def test_extract_accepts_bare_username(monkeypatch):
    from src.extractors import github_extractor as G
    monkeypatch.setattr(G, "_fetch_github_profile",
                        lambda login: {"login": login, "name": "Octo Cat",
                                       "html_url": f"https://github.com/{login}"})
    recs = list(G.GithubExtractor().extract("octocat"))
    assert recs and recs[0].fields["full_name"].value == "Octo Cat"
    # A filename (has a dot) is NOT treated as a username -> no fetch, no records.
    assert list(G.GithubExtractor().extract("missing.json")) == []


def test_github_handle_mismatch_with_resume_penalizes(monkeypatch):
    from src.extractors import github_extractor as G
    # Fetched profile shares Jane's CSV email (so they merge) but a DIFFERENT
    # github handle than the CSV/resume's "janedoe".
    monkeypatch.setattr(
        G, "_fetch_github_profile",
        lambda login: {"login": login, "name": "Jane Doe",
                       "email": "jane.doe@gmail.com",
                       "html_url": f"https://github.com/{login}"})
    clean = run([Source("csv", CSV)])
    jane0 = next(c for c in clean.candidates if c.full_name.value == "Jane Doe")
    result = run([Source("csv", CSV), Source("github", "janedoe-alt")])
    jane = next(c for c in result.candidates if c.full_name.value == "Jane Doe")
    rep = next(r for r in result.reports if r.candidate_id == jane.candidate_id)
    assert any(i.code == "github_mismatch" for i in rep.issues)
    # The mismatch lowers the candidate's overall confidence.
    assert jane.record_confidence < jane0.record_confidence


def test_github_mismatch_detected_even_when_profile_does_not_merge(monkeypatch):
    from src.extractors import github_extractor as G
    # Emailless profile with an unrelated name -> the fetch becomes its OWN
    # candidate, NOT merged with Jane. The mismatch must still be caught on Jane.
    monkeypatch.setattr(
        G, "_fetch_github_profile",
        lambda login: {"login": login, "name": "Totally Different Person",
                       "html_url": f"https://github.com/{login}"})
    result = run([Source("csv", CSV), Source("github", "not-jane")])
    jane = next(c for c in result.candidates if c.full_name.value == "Jane Doe")
    rep = next(r for r in result.reports if r.candidate_id == jane.candidate_id)
    assert any(i.code == "github_mismatch" for i in rep.issues)


def test_github_handle_match_with_resume_is_clean(monkeypatch):
    from src.extractors import github_extractor as G
    monkeypatch.setattr(
        G, "_fetch_github_profile",
        lambda login: {"login": login, "name": "Jane Doe",
                       "email": "jane.doe@gmail.com",
                       "html_url": f"https://github.com/{login}"})
    result = run([Source("csv", CSV), Source("github", "janedoe")])
    jane = next(c for c in result.candidates if c.full_name.value == "Jane Doe")
    rep = next(r for r in result.reports if r.candidate_id == jane.candidate_id)
    assert not any(i.code == "github_mismatch" for i in rep.issues)
