from datetime import UTC, datetime
from pathlib import Path

from diarist.run_output import create_run_directory, slugify


def test_slugify_french_filename() -> None:
    assert slugify("Réunion équipe #2") == "reunion-equipe-2"


def test_creates_sortable_collision_safe_run_directory(tmp_path: Path) -> None:
    now = datetime(2026, 8, 25, 14, 30, 12, tzinfo=UTC)
    first, stem = create_run_directory(tmp_path, Path("Réunion.m4a"), now=now)
    second, _ = create_run_directory(tmp_path, Path("Réunion.m4a"), now=now)

    assert stem == "reunion"
    assert first.name == "reunion-20260825T143012Z"
    assert second.name == "reunion-20260825T143012Z-01"
