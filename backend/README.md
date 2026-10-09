# Diarist — Backend

Multi-speaker transcription API. Uses
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CUDA or CPU) or
[mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)
(Apple Silicon/Metal, native only) for word-timestamped transcription in any
Whisper-supported language, and
[pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
for speaker diarization. Produces timestamped JSON and a formatted DOCX per
job.

Jobs run one at a time on a single background worker, matching one
transcription model held in memory. Uploads, job state, and finished
transcripts persist on disk under `JOB_DATA_DIR` so the API survives
restarts; model weights persist under `HF_HOME` so they are downloaded once.

There is no cleanup/rewrite pass (e.g. via a local LLM) in this release —
only the raw Whisper transcript, grouped into speaker turns.

## Hardware/backend selection

See the [repo root README](../README.md#hardwarebackends) for the full
picture. Short version: `src/diarist/devices.py` auto-detects everything
(`WHISPER_BACKEND`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`,
`DIARIZATION_DEVICE`, all overridable), except that **mlx-whisper (Apple
Silicon/Metal) only works running natively, never inside Docker, on any
host**. In a container, faster-whisper (CUDA if the container was given a
GPU, else CPU) is the only option.

## Requirements

- Python 3.11
- [`uv`](https://docs.astral.sh/uv/)
- FFmpeg
- A Hugging Face read token with the Community-1 conditions accepted
- Optional, for real transcription speed: an NVIDIA GPU (CUDA 12.x), or
  Apple Silicon + `uv sync --extra mlx` (native run only). Without either,
  faster-whisper still works on CPU, just slower.

## Configuration

Copy `.env.example` to `.env` and set `HF_TOKEN`. See that file for every
other setting (backend/model choice, cache/job directories, devices, CORS).

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```

Run the API locally:

```bash
uv run diarist-api
```

On Apple Silicon, `uv sync --extra mlx` first and set `WHISPER_BACKEND=mlx`
(or leave it on `auto`) for Metal-accelerated transcription.

## API

- `GET /api/health`
- `GET /api/languages` — Whisper-supported language codes for the UI's picker
- `POST /api/jobs` — multipart upload: `file`, optional `language` (default
  `en`; pass `auto` for language auto-detection), `speakers`, `initial_prompt`
- `GET /api/jobs` — most recent first
- `GET /api/jobs/{id}`
- `DELETE /api/jobs/{id}`
- `GET /api/jobs/{id}/download/json`
- `GET /api/jobs/{id}/download/docx`

## Container image

```bash
docker build -t diarist-backend .
```

The image only supports faster-whisper (CUDA or CPU) — see `Dockerfile` for
the base image. `mlx-whisper` is never installed here; it has no Linux
wheels and wouldn't work in a container even if it did (no Metal
passthrough in Docker Desktop's Linux VM). If you run multiple GPU
workloads on one card, look into NVIDIA's
[time-slicing or MPS](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html)
features to share it between containers.
