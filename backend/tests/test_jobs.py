import json
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from diarist.jobs import JobError, JobManager
from diarist.models import Transcript, Utterance, Word


def test_tolerates_unreadable_lost_and_found(tmp_path: Path) -> None:
    """Fresh ext4 volumes ship a root-owned, non-root-readable lost+found
    directory. JobManager must skip it instead of crashing (startup calls
    _resume_pending_jobs, which used to stat() every entry unconditionally)."""
    lost_found = tmp_path / "lost+found"
    lost_found.mkdir()
    lost_found.chmod(0o000)
    try:
        manager = JobManager(tmp_path, engine=MagicMock())
        assert manager.list_jobs(owner_id="user_a") == []
    finally:
        lost_found.chmod(0o700)


def test_list_jobs_ignores_non_job_entries(tmp_path: Path) -> None:
    (tmp_path / "not-a-job-dir").mkdir()
    (tmp_path / "stray-file.txt").write_text("hello")

    manager = JobManager(tmp_path, engine=MagicMock())

    assert manager.list_jobs(owner_id="user_a") == []


def _fake_transcript() -> Transcript:
    return Transcript(
        source=Path("audio.wav"),
        language="en",
        requested_language="en",
        duration=1.0,
        model="faster-whisper:test",
        diarization_model="test",
        requested_speakers=None,
        speakers=["SPEAKER_00"],
        utterances=[Utterance(0.0, 1.0, "SPEAKER_00", "hello", [Word(0.0, 1.0, " hello")], id=1)],
    )


def _create_and_wait(manager: JobManager, owner_id: str = "user_a") -> str:
    record = manager.create_job(
        owner_id=owner_id,
        filename="test.wav",
        content=b"fake-audio-bytes",
        language="en",
        speakers=None,
        initial_prompt=None,
    )
    manager._queue.join()  # block until the background worker finishes this job
    return record.id


def test_owner_is_required_and_persisted_across_restart(tmp_path: Path) -> None:
    engine = MagicMock()
    engine.transcribe.return_value = _fake_transcript()
    manager = JobManager(tmp_path, engine=engine)
    job_id = _create_and_wait(manager)
    restarted = JobManager(tmp_path, engine=engine)
    assert restarted.get_job(job_id, owner_id="user_a").owner_id == "user_a"
    assert len(restarted.list_jobs(owner_id="user_a")) == 1
    assert restarted.list_jobs(owner_id="user_b") == []
    for operation in (
        lambda: restarted.get_job(job_id, owner_id="user_b"),
        lambda: restarted.output_path(job_id, "json", owner_id="user_b"),
        lambda: restarted.open_output(job_id, "json", owner_id="user_b"),
        lambda: restarted.open_output(job_id, "docx", owner_id="user_b"),
        lambda: restarted.delete_job(job_id, owner_id="user_b"),
    ):
        with pytest.raises(JobError, match="Job not found"):
            operation()
    with pytest.raises(TypeError):
        restarted.get_job(job_id)
    assert restarted.output_path(job_id, "json", owner_id="user_a").is_file()


def test_completed_job_records_processing_duration(tmp_path: Path) -> None:
    engine = MagicMock()
    engine.transcribe.return_value = _fake_transcript()
    manager = JobManager(tmp_path, engine=engine)

    job_id = _create_and_wait(manager)
    record = manager.get_job(job_id, owner_id="user_a")

    assert record.status == "completed"
    assert record.started_at is not None
    assert record.completed_at is not None
    assert record.started_at <= record.completed_at


def test_failed_job_still_records_completion_time(tmp_path: Path) -> None:
    engine = MagicMock()
    engine.transcribe.side_effect = RuntimeError("boom")
    manager = JobManager(tmp_path, engine=engine)

    job_id = _create_and_wait(manager)
    record = manager.get_job(job_id, owner_id="user_a")

    assert record.status == "failed"
    assert record.started_at is not None
    assert record.completed_at is not None


@pytest.mark.parametrize("status", ["queued", "processing", "completed"])
def test_legacy_ownerless_jobs_are_hidden_and_not_resumed(tmp_path: Path, status: str) -> None:
    engine = MagicMock()
    engine.transcribe.return_value = _fake_transcript()
    manager = JobManager(tmp_path, engine=engine)
    job_id = _create_and_wait(manager)
    path = tmp_path / job_id / "job.json"
    data = json.loads(path.read_text())
    del data["owner_id"]
    data["status"] = status
    path.write_text(json.dumps(data))
    engine.reset_mock()
    restarted = JobManager(tmp_path, engine=engine)
    restarted._queue.join()
    engine.transcribe.assert_not_called()
    assert restarted.list_jobs(owner_id="user_a") == []
    assert json.loads(path.read_text())["status"] == status
    with pytest.raises(JobError):
        restarted.get_job(job_id, owner_id="user_a")


@pytest.mark.parametrize("job_id", ["../outside", "/tmp/outside", "..", "bad", "a/b"])
def test_rejects_invalid_job_ids(tmp_path: Path, job_id: str) -> None:
    manager = JobManager(tmp_path, engine=MagicMock())
    with pytest.raises(JobError, match="^Job not found$"):
        manager.get_job(job_id, owner_id="user_a")
    for kind in ("json", "docx"):
        with pytest.raises(JobError, match="^Job not found$"):
            manager.open_output(job_id, kind, owner_id="user_a")


@pytest.mark.parametrize("target", ["job", "job.json", "output", "transcript.json"])
def test_rejects_symlink_escapes(tmp_path: Path, target: str) -> None:
    engine = MagicMock()
    engine.transcribe.return_value = _fake_transcript()
    manager = JobManager(tmp_path / "jobs", engine=engine)
    job_id = _create_and_wait(manager)
    job_dir = manager.data_dir / job_id
    original = {
        "job": job_dir,
        "job.json": job_dir / "job.json",
        "output": job_dir / "output",
        "transcript.json": job_dir / "output" / "transcript.json",
    }[target]
    outside = tmp_path / "outside"
    original.rename(outside)
    original.symlink_to(outside, target_is_directory=outside.is_dir())
    for operation in (manager.output_path, manager.open_output):
        with pytest.raises(JobError, match="^Job not found$"):
            operation(job_id, "json", owner_id="user_a")
    assert outside.exists()


def test_delete_during_transcription_does_not_resurrect_job(tmp_path: Path) -> None:
    started, finish = threading.Event(), threading.Event()

    def transcribe(*args, **kwargs):
        started.set()
        assert finish.wait(5)
        return _fake_transcript()

    engine = MagicMock()
    engine.transcribe.side_effect = transcribe
    manager = JobManager(tmp_path, engine=engine)
    record = manager.create_job(
        owner_id="user_a",
        filename="test.wav",
        content=b"audio",
        language="en",
        speakers=None,
        initial_prompt=None,
    )
    assert started.wait(5)
    manager.delete_job(record.id, owner_id="user_a")
    finish.set()
    manager._queue.join()
    assert not (tmp_path / record.id).exists()


def test_worker_error_does_not_expose_internal_paths(tmp_path: Path) -> None:
    engine = MagicMock()
    engine.transcribe.side_effect = RuntimeError(f"cannot open {tmp_path}/private/file")
    manager = JobManager(tmp_path, engine=engine)
    job_id = _create_and_wait(manager)
    error = manager.get_job(job_id, owner_id="user_a").error
    assert error and str(tmp_path) not in error


def test_active_deletion_is_durable_across_restart(tmp_path: Path) -> None:
    started, finish = threading.Event(), threading.Event()

    def transcribe(*args, **kwargs):
        started.set()
        assert finish.wait(5)
        return _fake_transcript()

    engine = MagicMock()
    engine.transcribe.side_effect = transcribe
    manager = JobManager(tmp_path, engine=engine)
    record = manager.create_job(
        owner_id="user_a",
        filename="test.wav",
        content=b"audio",
        language="en",
        speakers=None,
        initial_prompt=None,
    )
    assert started.wait(5)
    try:
        manager.delete_job(record.id, owner_id="user_a")
        restarted_engine = MagicMock()
        restarted_engine.transcribe.return_value = _fake_transcript()
        restarted = JobManager(tmp_path, engine=restarted_engine)
        restarted._queue.join()
        restarted_engine.transcribe.assert_not_called()
        assert restarted.list_jobs(owner_id="user_a") == []
    finally:
        finish.set()
        manager._queue.join()


@pytest.mark.parametrize("data", ["not-json", "[]", '{"options": "bad"}'])
def test_malformed_records_do_not_break_startup_or_listing(tmp_path: Path, data: str) -> None:
    job_id = "20260101T000000Z-12345678"
    path = tmp_path / job_id / "job.json"
    path.parent.mkdir()
    path.write_text(data)
    manager = JobManager(tmp_path, engine=MagicMock())
    assert manager.list_jobs(owner_id="user_a") == []
    with pytest.raises(JobError, match="^Job not found$"):
        manager.get_job(job_id, owner_id="user_a")


@pytest.mark.parametrize("status", ["queued", "processing"])
def test_owned_pending_jobs_resume_with_owner_intact(tmp_path: Path, status: str) -> None:
    engine = MagicMock()
    engine.transcribe.return_value = _fake_transcript()
    manager = JobManager(tmp_path, engine=engine)
    job_id = _create_and_wait(manager)
    path = tmp_path / job_id / "job.json"
    data = json.loads(path.read_text())
    data["status"] = status
    path.write_text(json.dumps(data))
    engine.reset_mock()
    restarted = JobManager(tmp_path, engine=engine)
    restarted._queue.join()
    engine.transcribe.assert_called_once()
    assert restarted.get_job(job_id, owner_id="user_a").status == "completed"
    assert restarted.list_jobs(owner_id="user_b") == []
