from __future__ import annotations

import json
import logging
import queue
import shutil
import threading
import traceback
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .audio import AudioError
from .languages import is_supported
from .models import Transcript
from .output import write_docx, write_json
from .transcribe import TranscriptionEngine, TranscriptionError

logger = logging.getLogger("diarist.jobs")

JobStatus = Literal["queued", "processing", "completed", "failed"]

JOB_FILE = "job.json"
INPUT_DIR = "input"
OUTPUT_DIR = "output"
TRANSCRIPT_JSON = "transcript.json"
TRANSCRIPT_DOCX = "transcript.docx"


class JobError(RuntimeError):
    pass


@dataclass
class JobOptions:
    language: str | None = None
    speakers: int | None = None
    initial_prompt: str | None = None


@dataclass
class JobRecord:
    id: str
    original_filename: str
    status: JobStatus
    created_at: str
    options: JobOptions
    updated_at: str = ""
    error: str | None = None
    transcript: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "options": {
                "language": self.options.language,
                "speakers": self.options.speakers,
                "initial_prompt": self.options.initial_prompt,
            },
            "error": self.error,
            "transcript": self.transcript,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobRecord:
        options = data.get("options") or {}
        return cls(
            id=str(data["id"]),
            original_filename=str(data["original_filename"]),
            status=data["status"],
            created_at=str(data["created_at"]),
            updated_at=str(data.get("updated_at", "")),
            options=JobOptions(
                language=options.get("language"),
                speakers=options.get("speakers"),
                initial_prompt=options.get("initial_prompt"),
            ),
            error=data.get("error"),
            transcript=data.get("transcript"),
        )


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class JobManager:
    """Persists jobs on disk and runs them one at a time on a background worker.

    A single-worker queue matches the deployment's single shared GPU slot:
    exactly one transcription (Whisper + diarization) runs at a time, while
    the API stays responsive for uploads, status polling, and downloads of
    already-finished jobs.
    """

    def __init__(self, data_dir: Path, engine: TranscriptionEngine) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.engine = engine
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._worker = threading.Thread(target=self._run_worker, daemon=True)
        self._resume_pending_jobs()
        self._worker.start()

    # -- paths -----------------------------------------------------------

    def _job_dir(self, job_id: str) -> Path:
        return self.data_dir / job_id

    def _job_file(self, job_id: str) -> Path:
        return self._job_dir(job_id) / JOB_FILE

    # -- persistence -------------------------------------------------------

    def _write_record(self, record: JobRecord) -> None:
        record.updated_at = _now()
        path = self._job_file(record.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), "utf-8")

    def _read_record(self, job_id: str) -> JobRecord:
        path = self._job_file(job_id)
        try:
            return JobRecord.from_dict(json.loads(path.read_text("utf-8")))
        except FileNotFoundError as exc:
            raise JobError(f"Job not found: {job_id}") from exc

    def _resume_pending_jobs(self) -> None:
        """Re-enqueue jobs left queued/processing by an earlier pod."""
        if not self.data_dir.exists():
            return
        for job_dir in sorted(self.data_dir.iterdir()):
            job_file = job_dir / JOB_FILE
            if not job_file.exists():
                continue
            record = self._read_record(job_dir.name)
            if record.status in ("queued", "processing"):
                record.status = "queued"
                self._write_record(record)
                self._queue.put(record.id)
                logger.info("Resuming interrupted job %s", record.id)

    # -- public API --------------------------------------------------------

    def create_job(
        self,
        *,
        filename: str,
        content: bytes,
        language: str | None,
        speakers: int | None,
        initial_prompt: str | None,
    ) -> JobRecord:
        if language is not None and not is_supported(language):
            raise JobError(f"Unsupported language code: {language!r}")
        suffix = Path(filename).suffix.lower()
        if suffix not in {".m4a", ".mp3", ".wav"}:
            raise JobError(f"Unsupported audio type {suffix!r}; use .m4a, .mp3, or .wav")

        job_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        job_dir = self._job_dir(job_id)
        input_dir = job_dir / INPUT_DIR
        input_dir.mkdir(parents=True, exist_ok=True)
        input_path = input_dir / f"audio{suffix}"
        input_path.write_bytes(content)

        record = JobRecord(
            id=job_id,
            original_filename=filename,
            status="queued",
            created_at=_now(),
            options=JobOptions(language=language, speakers=speakers, initial_prompt=initial_prompt),
        )
        self._write_record(record)
        self._queue.put(job_id)
        return record

    def get_job(self, job_id: str) -> JobRecord:
        with self._lock:
            return self._read_record(job_id)

    def list_jobs(self) -> list[JobRecord]:
        if not self.data_dir.exists():
            return []
        records = []
        for job_dir in self.data_dir.iterdir():
            if (job_dir / JOB_FILE).exists():
                with self._lock:
                    records.append(self._read_record(job_dir.name))
        return sorted(records, key=lambda record: record.created_at, reverse=True)

    def output_path(self, job_id: str, kind: Literal["json", "docx"]) -> Path:
        name = TRANSCRIPT_JSON if kind == "json" else TRANSCRIPT_DOCX
        path = self._job_dir(job_id) / OUTPUT_DIR / name
        if not path.exists():
            raise JobError(f"No {kind} output for job {job_id} (is it completed?)")
        return path

    def delete_job(self, job_id: str) -> None:
        with self._lock:
            job_dir = self._job_dir(job_id)
            if not job_dir.exists():
                raise JobError(f"Job not found: {job_id}")
            shutil.rmtree(job_dir)

    # -- worker --------------------------------------------------------------

    def _run_worker(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._process_job(job_id)
            except Exception:
                logger.exception("Unhandled error processing job %s", job_id)
            finally:
                self._queue.task_done()

    def _process_job(self, job_id: str) -> None:
        with self._lock:
            record = self._read_record(job_id)
            record.status = "processing"
            record.error = None
            self._write_record(record)

        job_dir = self._job_dir(job_id)
        input_dir = job_dir / INPUT_DIR
        audio_files = list(input_dir.glob("audio.*"))
        if not audio_files:
            self._fail(job_id, "Input audio file is missing.")
            return
        audio_path = audio_files[0]
        work_dir = job_dir / "work"
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            transcript: Transcript = self.engine.transcribe(
                audio_path,
                num_speakers=record.options.speakers,
                language=record.options.language,
                initial_prompt=record.options.initial_prompt,
                work_dir=work_dir,
            )
        except (AudioError, TranscriptionError) as exc:
            self._fail(job_id, str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.error("Job %s failed: %s\n%s", job_id, exc, traceback.format_exc())
            self._fail(job_id, f"Unexpected error: {exc}")
            return
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        output_dir = job_dir / OUTPUT_DIR
        json_path = output_dir / TRANSCRIPT_JSON
        docx_path = output_dir / TRANSCRIPT_DOCX
        write_json(transcript, json_path)
        write_docx(transcript, docx_path)

        with self._lock:
            record = self._read_record(job_id)
            record.status = "completed"
            record.transcript = transcript.to_dict()
            self._write_record(record)

    def _fail(self, job_id: str, message: str) -> None:
        with self._lock:
            record = self._read_record(job_id)
            record.status = "failed"
            record.error = message
            self._write_record(record)
