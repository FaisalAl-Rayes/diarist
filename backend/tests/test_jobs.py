from pathlib import Path
from unittest.mock import MagicMock

from diarist.jobs import JobManager
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
        assert manager.list_jobs() == []
    finally:
        lost_found.chmod(0o700)


def test_list_jobs_ignores_non_job_entries(tmp_path: Path) -> None:
    (tmp_path / "not-a-job-dir").mkdir()
    (tmp_path / "stray-file.txt").write_text("hello")

    manager = JobManager(tmp_path, engine=MagicMock())

    assert manager.list_jobs() == []


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
        utterances=[
            Utterance(0.0, 1.0, "SPEAKER_00", "hello", [Word(0.0, 1.0, " hello")], id=1)
        ],
    )


def _create_and_wait(manager: JobManager) -> str:
    record = manager.create_job(
        filename="test.wav",
        content=b"fake-audio-bytes",
        language="en",
        speakers=None,
        initial_prompt=None,
    )
    manager._queue.join()  # block until the background worker finishes this job
    return record.id


def test_completed_job_records_processing_duration(tmp_path: Path) -> None:
    engine = MagicMock()
    engine.transcribe.return_value = _fake_transcript()
    manager = JobManager(tmp_path, engine=engine)

    job_id = _create_and_wait(manager)
    record = manager.get_job(job_id)

    assert record.status == "completed"
    assert record.started_at is not None
    assert record.completed_at is not None
    assert record.started_at <= record.completed_at


def test_failed_job_still_records_completion_time(tmp_path: Path) -> None:
    engine = MagicMock()
    engine.transcribe.side_effect = RuntimeError("boom")
    manager = JobManager(tmp_path, engine=engine)

    job_id = _create_and_wait(manager)
    record = manager.get_job(job_id)

    assert record.status == "failed"
    assert record.started_at is not None
    assert record.completed_at is not None
