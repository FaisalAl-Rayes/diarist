from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "transcription"


def create_run_directory(
    output_root: Path,
    source: Path,
    *,
    name: str | None = None,
    now: datetime | None = None,
) -> tuple[Path, str]:
    """Create a sortable, collision-safe directory for one transcription run."""
    output_root = output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    artifact_stem = slugify(name or source.stem)
    base = f"{artifact_stem}-{stamp}"
    for suffix in range(1000):
        candidate = output_root / (base if suffix == 0 else f"{base}-{suffix:02d}")
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate, artifact_stem
    raise RuntimeError(f"Could not create a unique run directory under {output_root}")
