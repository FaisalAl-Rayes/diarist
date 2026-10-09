from pathlib import Path
from unittest.mock import MagicMock

from diarist.jobs import JobManager


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
