"""FastAPI adapter — a thin shell over the pure pipeline.

The web layer knows nothing about merge/normalize/resolve logic; it only handles
HTTP, saves uploads to temp files, calls `pipeline.run(...)`, and serializes.
This boundary is what keeps the engine unit-testable without HTTP and keeps the
determinism guarantee provable (docs/DESIGN.md §7).

Endpoints:
    POST /api/run         multipart upload -> { run_id, candidates, validation, timings }
    POST /api/project     { run_id, projection_id | projection } -> { output }
    GET  /api/projections -> available saved projection configs
    GET  /api/health
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..pipeline import Source, run
from ..projection.engine import project
from ..projection.loader import from_dict, load_projection
from ..serialize import candidate_to_dict
from . import store

_SAMPLES = Path(__file__).resolve().parents[2] / "samples"
_WEB = Path(__file__).resolve().parents[2] / "web"

app = FastAPI(title="Candidate Data Transformation Engine", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only; the UI is served separately
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- helpers ------------------------------------------------------------------

def _save_temp(upload: UploadFile, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as fh:
        fh.write(upload.file.read())
    return path


def _projection_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for pattern in ("projection_*.yaml", "projection_*.yml", "projection_*.json"):
        for p in _SAMPLES.glob(pattern):
            files[p.stem] = p
    return files


# --- request models -----------------------------------------------------------

class ProjectRequest(BaseModel):
    run_id: str
    projection_id: str | None = None
    projection: dict[str, Any] | None = None


# --- endpoints ----------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/projections")
def list_projections() -> dict:
    out = []
    for pid, path in sorted(_projection_files().items()):
        cfg = load_projection(path)
        out.append({"id": pid, "name": cfg.name,
                    "fields": [m.out for m in cfg.fields]})
    return {"projections": out}


@app.post("/api/run")
async def run_pipeline(
    csv: list[UploadFile] = File(default=[]),
    resume: list[UploadFile] = File(default=[]),
    ats: list[UploadFile] = File(default=[]),    # ATS export JSON file(s)
    notes: list[UploadFile] = File(default=[]),  # recruiter notes .txt file(s)
    github: list[str] = Form(default=[]),        # GitHub profile URL(s)
    linkedin: list[str] = Form(default=[]),      # LinkedIn id to VERIFY (not a source)
) -> dict:
    github = [u for u in github if u.strip()]
    linkedin_id = next((u.strip() for u in linkedin if u.strip()), None)
    if not csv and not resume and not ats and not notes and not github:
        raise HTTPException(
            400, "provide at least one csv/resume/ats/notes file or github url")

    sources: list[Source] = []
    temps: list[str] = []
    try:
        for up in csv:
            path = _save_temp(up, ".csv")
            temps.append(path)
            sources.append(Source("csv", path))
        for up in resume:
            path = _save_temp(up, ".pdf")
            temps.append(path)
            sources.append(Source("resume_pdf", path))
        for up in ats:
            path = _save_temp(up, ".json")
            temps.append(path)
            sources.append(Source("ats_json", path))
        for up in notes:
            path = _save_temp(up, ".txt")
            temps.append(path)
            sources.append(Source("notes", path))
        for url in github:
            sources.append(Source("github", url.strip()))

        result = run(sources, linkedin_id=linkedin_id)
    finally:
        for path in temps:
            try:
                os.unlink(path)
            except OSError:
                pass

    run_id = store.put(result.candidates)
    return {
        "run_id": run_id,
        "candidates": [candidate_to_dict(c) for c in result.candidates],
        "validation": [r.to_dict() for r in result.reports],
        "timings_ms": result.stats.stage_timings_ms,
        "stats": {"records_in": result.stats.records_in,
                  "clusters_out": result.stats.clusters_out,
                  "conflicts_found": result.stats.conflicts_found},
    }


@app.post("/api/project")
def project_run(req: ProjectRequest) -> dict:
    candidates = store.get(req.run_id)
    if candidates is None:
        raise HTTPException(404, f"unknown run_id {req.run_id!r}")

    if req.projection is not None:
        cfg = from_dict(req.projection)
    elif req.projection_id is not None:
        files = _projection_files()
        if req.projection_id not in files:
            raise HTTPException(404, f"unknown projection {req.projection_id!r}")
        cfg = load_projection(files[req.projection_id])
    else:
        raise HTTPException(400, "provide projection_id or projection")

    return {"output": [project(c, cfg) for c in candidates]}


# Serve the minimal UI from "/" — mounted LAST so the /api/* routes above take
# precedence over the static catch-all (Starlette matches routes in order).
if _WEB.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB), html=True), name="ui")
