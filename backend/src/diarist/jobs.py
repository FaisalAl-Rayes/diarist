from __future__ import annotations

import json
import logging
import queue
import re
import shutil
import threading
import traceback
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO, Literal

from .audio import AudioError
from .languages import is_supported
from .models import Transcript
from .output import write_docx, write_json
from .transcribe import TranscriptionEngine, TranscriptionError

logger = logging.getLogger("diarist.jobs")

JobStatus = Literal["queued", "processing", "completed", "failed"]

JOB_FILE = "job.json"
DELETED_FILE = ".deleted"
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
    owner_id: str
    original_filename: str
    status: JobStatus
    created_at: str
    options: JobOptions
    updated_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    transcript: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "original_filename": self.original_filename,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
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
            owner_id=data.get("owner_id", ""),
            original_filename=str(data["original_filename"]),
            status=data["status"],
            created_at=str(data["created_at"]),
            updated_at=str(data.get("updated_at", "")),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
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
        self.data_dir = data_dir.resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.engine = engine
        self._lock = threading.Lock()
        self._active: set[str] = set()
        self._deleted: set[str] = set()
        self._queue: queue.Queue[str] = queue.Queue()
        self._worker = threading.Thread(target=self._run_worker, daemon=True)
        self._resume_pending_jobs()
        self._worker.start()

    # -- paths -----------------------------------------------------------

    def _job_dir(self, job_id: str) -> Path:
        if not re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", job_id):
            raise JobError("Job not found")
        return self._safe_path(self.data_dir / job_id)

    def _safe_path(self, path: Path) -> Path:
        """Reject symlinks at every component, even ones pointing within storage."""
        try:
            relative = path.relative_to(self.data_dir)
            current = self.data_dir
            for part in relative.parts:
                current = current / part
                if current.is_symlink():
                    raise JobError("Job not found")
            if not path.resolve().is_relative_to(self.data_dir):
                raise JobError("Job not found")
        except (OSError, ValueError) as exc:
            raise JobError("Job not found") from exc
        return path

    def _job_file(self, job_id: str) -> Path:
        return self._safe_path(self._job_dir(job_id) / JOB_FILE)

    # -- persistence -------------------------------------------------------

    def _write_record(self, record: JobRecord) -> None:
        record.updated_at = _now()
        path = self._job_file(record.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), "utf-8")

    def _read_record(self, job_id: str) -> JobRecord:
        path = self._job_file(job_id)
        try:
            if self._safe_path(path.parent / DELETED_FILE).exists():
                raise JobError("Job not found")
            record = JobRecord.from_dict(json.loads(path.read_text("utf-8")))
            if record.id != job_id or job_id in self._deleted:
                raise JobError("Job not found")
            return record
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise JobError("Job not found") from exc

    def _iter_job_dirs(self) -> list[Path]:
        """List job directories, tolerating filesystem cruft.

        Fresh ext4 volumes (common on container storage/CSI backends) can
        contain reserved entries like `lost+found`, owned by root and
        unreadable by this process's non-root user. A single unreadable or
        malformed entry must not crash startup or job listing for everyone
        else.
        """
        job_dirs = []
        for entry in sorted(self.data_dir.iterdir()):
            if entry.name == "lost+found":
                continue
            try:
                self._job_dir(entry.name)
                if not entry.is_dir():
                    continue
                if not (entry / JOB_FILE).exists():
                    continue
                self._read_record(entry.name)
            except (OSError, JobError):
                logger.warning("Skipping unreadable entry in %s: %s", self.data_dir, entry.name)
                continue
            job_dirs.append(entry)
        return job_dirs

    def _resume_pending_jobs(self) -> None:
        """Re-enqueue jobs left queued/processing by an earlier pod."""
        if not self.data_dir.exists():
            return
        # A crash after deleting an active job must not resume it. Finish the
        # deferred removal before scanning resumable records.
        for entry in self.data_dir.iterdir():
            try:
                job_dir = self._job_dir(entry.name)
                if self._safe_path(job_dir / DELETED_FILE).is_file():
                    shutil.rmtree(job_dir)
            except (JobError, OSError):
                continue
        for job_dir in self._iter_job_dirs():
            record = self._read_record(job_dir.name)
            if (
                isinstance(record.owner_id, str)
                and record.owner_id.strip()
                and record.status in ("queued", "processing")
            ):
                record.status = "queued"
                self._write_record(record)
                self._queue.put(record.id)
                logger.info("Resuming interrupted job %s", record.id)

    # -- public API --------------------------------------------------------

    def create_job(
        self,
        *,
        owner_id: str,
        filename: str,
        content: bytes,
        language: str | None,
        speakers: int | None,
        initial_prompt: str | None,
    ) -> JobRecord:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise JobError("Owner is required")
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
            owner_id=owner_id,
            original_filename=filename,
            status="queued",
            created_at=_now(),
            options=JobOptions(language=language, speakers=speakers, initial_prompt=initial_prompt),
        )
        self._write_record(record)
        self._queue.put(job_id)
        return record

    def _owned_record(self, job_id: str, owner_id: str) -> JobRecord:
        record = self._read_record(job_id)
        if not owner_id or not record.owner_id or record.owner_id != owner_id:
            raise JobError("Job not found")
        return record

    def get_job(self, job_id: str, *, owner_id: str) -> JobRecord:
        with self._lock:
            return self._owned_record(job_id, owner_id)

    def list_jobs(self, *, owner_id: str) -> list[JobRecord]:
        if not self.data_dir.exists():
            return []
        with self._lock:
            records = [self._read_record(job_dir.name) for job_dir in self._iter_job_dirs()]
        return sorted(
            [record for record in records if record.owner_id and record.owner_id == owner_id],
            key=lambda record: record.created_at,
            reverse=True,
        )

    def _owned_output_path(
        self, job_id: str, kind: Literal["json", "docx"], owner_id: str
    ) -> Path:
        self._owned_record(job_id, owner_id)
        name = TRANSCRIPT_JSON if kind == "json" else TRANSCRIPT_DOCX
        path = self._safe_path(self._job_dir(job_id) / OUTPUT_DIR / name)
        if not path.exists():
            raise JobError("Job not found")
        return path

    def output_path(self, job_id: str, kind: Literal["json", "docx"], *, owner_id: str) -> Path:
        with self._lock:
            return self._owned_output_path(job_id, kind, owner_id)

    def open_output(self, job_id: str, kind: Literal["json", "docx"], *, owner_id: str) -> BinaryIO:
        """Authorize and open atomically with deletion; the caller must close the handle."""
        with self._lock:
            path = self._owned_output_path(job_id, kind, owner_id)
            try:
                return path.open("rb")
            except OSError as exc:
                raise JobError("Job not found") from exc

    def delete_job(self, job_id: str, *, owner_id: str) -> None:
        with self._lock:
            self._owned_record(job_id, owner_id)
            job_dir = self._job_dir(job_id)
            if not job_dir.exists():
                raise JobError("Job not found")
            if job_id in self._active:
                # Hide immediately; defer physical removal until the engine stops writing.
                self._safe_path(job_dir / DELETED_FILE).touch()
                self._deleted.add(job_id)
            else:
                shutil.rmtree(job_dir)

    # -- worker --------------------------------------------------------------

    def _run_worker(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._process_job(job_id)
            except JobError:
                pass  # Deleted queued job, or unsafe/missing storage.
            except Exception:
                logger.exception("Unhandled error processing job %s", job_id)
                self._fail(job_id, "Transcription failed.")
            finally:
                with self._lock:
                    self._active.discard(job_id)
                    if job_id in self._deleted:
                        shutil.rmtree(self._job_dir(job_id), ignore_errors=True)
                        self._deleted.discard(job_id)
                self._queue.task_done()

    def _process_job(self, job_id: str) -> None:
        with self._lock:
            record = self._read_record(job_id)
            if not record.owner_id:
                return
            self._active.add(job_id)
            record.status = "processing"
            record.started_at = _now()
            record.error = None
            self._write_record(record)
            job_dir = self._job_dir(job_id)
            input_dir = self._safe_path(job_dir / INPUT_DIR)
            audio_files = [self._safe_path(path) for path in input_dir.glob("audio.*")]
            work_dir = self._safe_path(job_dir / "work")
            work_dir.mkdir(parents=True, exist_ok=True)
        if not audio_files:
            self._fail(job_id, "Input audio file is missing.")
            return
        audio_path = audio_files[0]

        try:
            transcript: Transcript = self.engine.transcribe(
                audio_path,
                num_speakers=record.options.speakers,
                language=record.options.language,
                initial_prompt=record.options.initial_prompt,
                work_dir=work_dir,
            )
        except (AudioError, TranscriptionError) as exc:
            logger.warning("Job %s failed: %s", job_id, exc)
            self._fail(job_id, "Transcription failed.")
            return
        except Exception as exc:  # noqa: BLE001
            logger.error("Job %s failed: %s\n%s", job_id, exc, traceback.format_exc())
            self._fail(job_id, "Transcription failed.")
            return
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        with self._lock:
            record = self._read_record(job_id)
            output_dir = self._safe_path(job_dir / OUTPUT_DIR)
            json_path = self._safe_path(output_dir / TRANSCRIPT_JSON)
            docx_path = self._safe_path(output_dir / TRANSCRIPT_DOCX)
            write_json(transcript, json_path)
            write_docx(transcript, docx_path)
            record.status = "completed"
            record.completed_at = _now()
            record.transcript = transcript.to_dict()
            self._write_record(record)

    def _fail(self, job_id: str, message: str) -> None:
        with self._lock:
            try:
                record = self._read_record(job_id)
            except JobError:
                return
            record.status = "failed"
            record.completed_at = _now()
            record.error = message
            self._write_record(record)
