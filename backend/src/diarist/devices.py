"""Hardware/backend auto-detection.

Three independent axes get decided here:

1. Whisper backend: faster-whisper (CUDA or CPU, works everywhere) or
   mlx-whisper (Apple Silicon only, via Metal). mlx-whisper cannot run
   inside Docker on any host -- Docker Desktop on macOS runs containers in a
   Linux VM with no Metal passthrough, so "detect the host architecture" is
   not a way around this. MLX only works when this process runs natively
   on macOS (e.g. `uv run diarist-api`), never in a container.
2. faster-whisper's device/compute_type: CUDA+float16 if a GPU is visible,
   else CPU+int8 (int8 is noticeably faster than float32 on CPU with a
   small accuracy cost).
3. pyannote's torch device: cuda > mps (Apple Silicon, native only) > cpu.
"""

from __future__ import annotations

import os
import platform


def is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def mlx_whisper_available() -> bool:
    """True only when mlx-whisper is installed and importable.

    Importing mlx_whisper on a non-Apple-Silicon host (including inside any
    Docker container, even one running on an Apple Silicon host) always
    fails -- the `mlx` package underneath it has no Linux or x86 wheels.
    """
    if not is_apple_silicon():
        return False
    try:
        import mlx_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def resolve_whisper_backend() -> str:
    """Return "mlx" or "faster-whisper", honoring WHISPER_BACKEND if set."""
    requested = os.getenv("WHISPER_BACKEND", "auto")
    if requested in ("mlx", "faster-whisper"):
        return requested
    if requested != "auto":
        raise ValueError(f"WHISPER_BACKEND must be auto, mlx, or faster-whisper, got {requested!r}")
    return "mlx" if mlx_whisper_available() else "faster-whisper"


def cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return torch.cuda.is_available()


def mps_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return torch.backends.mps.is_available()


def resolve_whisper_device() -> str:
    """faster-whisper only understands "cuda" and "cpu" (no MPS support in
    ctranslate2)."""
    requested = os.getenv("WHISPER_DEVICE", "auto")
    if requested != "auto":
        return requested
    return "cuda" if cuda_available() else "cpu"


def resolve_whisper_compute_type(device: str) -> str:
    requested = os.getenv("WHISPER_COMPUTE_TYPE", "auto")
    if requested != "auto":
        return requested
    return "float16" if device == "cuda" else "int8"


def resolve_diarization_device() -> str:
    requested = os.getenv("DIARIZATION_DEVICE", "auto")
    if requested != "auto":
        return requested
    if cuda_available():
        return "cuda"
    if mps_available():
        return "mps"
    return "cpu"
