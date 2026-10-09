from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

SUPPORTED_EXTENSIONS = {".m4a", ".mp3", ".wav"}


class AudioError(RuntimeError):
    pass


def validate_audio(path: Path) -> Path:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise AudioError(f"Audio file not found: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise AudioError(f"Unsupported audio type {path.suffix!r}; use {supported}")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise AudioError("ffmpeg and ffprobe are required (install with `brew install ffmpeg`).")
    return path


def normalize_audio(source: Path, destination: Path) -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise AudioError(f"ffmpeg could not decode {source}") from exc


def duration_seconds(path: Path) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return float(json.loads(result.stdout)["format"]["duration"])
    except (subprocess.CalledProcessError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise AudioError(f"Could not determine audio duration for {path}") from exc
