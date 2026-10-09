from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .jobs import JobError, JobManager
from .languages import SUPPORTED_LANGUAGES
from .transcribe import TranscriptionEngine

JOB_DATA_DIR = Path(os.getenv("JOB_DATA_DIR", "/data/jobs"))

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024 * 1024)))  # 2 GiB

app = FastAPI(title="Diarist", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine = TranscriptionEngine()
_jobs = JobManager(JOB_DATA_DIR, _engine)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/languages")
def languages() -> list[dict[str, str]]:
    return [{"code": "auto", "name": "Detect automatically"}] + [
        {"code": code, "name": name} for code, name in SUPPORTED_LANGUAGES.items()
    ]


@app.post("/api/jobs", status_code=201)
async def create_job(
    file: Annotated[UploadFile, File()],
    language: Annotated[str, Form()] = "en",
    speakers: Annotated[int | None, Form()] = None,
    initial_prompt: Annotated[str | None, Form()] = None,
) -> dict:
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_BYTES} bytes.")
    if not content:
        raise HTTPException(400, "Uploaded file is empty.")
    try:
        record = _jobs.create_job(
            filename=file.filename or "audio",
            content=content,
            language=language,
            speakers=speakers,
            initial_prompt=initial_prompt,
        )
    except JobError as exc:
        raise HTTPException(400, str(exc)) from exc
    return record.to_dict()


@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    return [record.to_dict() for record in _jobs.list_jobs()]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    try:
        return _jobs.get_job(job_id).to_dict()
    except JobError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str) -> None:
    try:
        _jobs.delete_job(job_id)
    except JobError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/jobs/{job_id}/download/json")
def download_json(job_id: str) -> FileResponse:
    try:
        path = _jobs.output_path(job_id, "json")
    except JobError as exc:
        raise HTTPException(404, str(exc)) from exc
    return FileResponse(path, filename=f"{job_id}-transcript.json", media_type="application/json")


@app.get("/api/jobs/{job_id}/download/docx")
def download_docx(job_id: str) -> FileResponse:
    try:
        path = _jobs.output_path(job_id, "docx")
    except JobError as exc:
        raise HTTPException(404, str(exc)) from exc
    return FileResponse(
        path,
        filename=f"{job_id}-transcript.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
