"""API tests — thin HTTP shell over the pipeline (FastAPI TestClient)."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from src.api.app import app

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CSV = SAMPLES / "candidates.csv"

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_serves_minimal_ui():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Canonical Inspector" in resp.text
    assert client.get("/app.js").status_code == 200
    assert client.get("/styles.css").status_code == 200


def test_list_projections_includes_samples():
    data = client.get("/api/projections").json()
    ids = {p["id"] for p in data["projections"]}
    assert "projection_ats" in ids
    assert "projection_minimal" in ids


def test_run_requires_a_file():
    assert client.post("/api/run").status_code == 400


def _run_csv() -> dict:
    with CSV.open("rb") as fh:
        resp = client.post("/api/run", files=[("csv", ("candidates.csv", fh, "text/csv"))])
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_run_returns_candidates_validation_and_timings():
    body = _run_csv()
    assert len(body["candidates"]) == 3
    assert len(body["validation"]) == 3
    assert "resolve" in body["timings_ms"]
    assert body["stats"]["records_in"] == 3
    assert body["run_id"]


def test_project_by_id_reuses_run_without_rerunning():
    run_id = _run_csv()["run_id"]
    resp = client.post("/api/project",
                       json={"run_id": run_id, "projection_id": "projection_ats"})
    assert resp.status_code == 200, resp.text
    out = resp.json()["output"]
    assert len(out) == 3
    assert "candidateName" in out[0]  # renamed field from the ATS config


def test_project_with_inline_config():
    run_id = _run_csv()["run_id"]
    inline = {"name": "inline", "fields": [{"canonical": "full_name", "out": "n"}]}
    resp = client.post("/api/project",
                       json={"run_id": run_id, "projection": inline})
    assert resp.status_code == 200
    assert "n" in resp.json()["output"][0]


def test_project_unknown_run_id_is_404():
    resp = client.post("/api/project",
                       json={"run_id": "doesnotexist", "projection_id": "projection_ats"})
    assert resp.status_code == 404
