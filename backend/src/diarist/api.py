from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Annotated, BinaryIO

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .auth import authenticated_user
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

_manager: JobManager | None = None
_manager_lock = threading.Lock()


def get_job_manager() -> JobManager:
    global _manager
    # functools.cache alone allows concurrent first calls to initialize multiple
    # workers on the same files. Initialization must be serialized too.
    with _manager_lock:
        if _manager is None:
            _manager = JobManager(JOB_DATA_DIR, TranscriptionEngine())
        return _manager


Owner = Annotated[str, Depends(authenticated_user)]
Jobs = Annotated[JobManager, Depends(get_job_manager)]


@app.middleware("http")
async def private_job_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/api/jobs" or request.url.path.startswith("/api/jobs/"):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers.append("Vary", "Authorization")
    return response


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
    owner_id: Owner,
    jobs: Jobs,
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
        record = jobs.create_job(
            owner_id=owner_id,
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
def list_jobs(owner_id: Owner, jobs: Jobs) -> list[dict]:
    return [record.to_dict() for record in jobs.list_jobs(owner_id=owner_id)]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, owner_id: Owner, jobs: Jobs) -> dict:
    try:
        return jobs.get_job(job_id, owner_id=owner_id).to_dict()
    except JobError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, owner_id: Owner, jobs: Jobs) -> None:
    try:
        jobs.delete_job(job_id, owner_id=owner_id)
    except JobError as exc:
        raise HTTPException(404, str(exc)) from exc


class DownloadResponse(StreamingResponse):
    """Stream an authorized open file, closing even on disconnect or send failure."""

    def __init__(self, file: BinaryIO, *, filename: str, media_type: str) -> None:
        self.file = file
        super().__init__(
            iter(lambda: file.read(64 * 1024), b""),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.file.close()


@app.get("/api/jobs/{job_id}/download/json")
def download_json(job_id: str, owner_id: Owner, jobs: Jobs) -> DownloadResponse:
    try:
        file = jobs.open_output(job_id, "json", owner_id=owner_id)
    except JobError as exc:
        raise HTTPException(404, str(exc)) from exc
    return DownloadResponse(file, filename=f"{job_id}-transcript.json", media_type="application/json")


@app.get("/api/jobs/{job_id}/download/docx")
def download_docx(job_id: str, owner_id: Owner, jobs: Jobs) -> DownloadResponse:
    try:
        file = jobs.open_output(job_id, "docx", owner_id=owner_id)
    except JobError as exc:
        raise HTTPException(404, str(exc)) from exc
    return DownloadResponse(
        file,
        filename=f"{job_id}-transcript.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
