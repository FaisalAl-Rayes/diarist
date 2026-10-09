# Diarist — Backend

GPU-accelerated multi-speaker transcription API. Uses
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) (large-v3) for
word-timestamped transcription in any Whisper-supported language, and
[pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
for speaker diarization. Produces timestamped JSON and a formatted DOCX per
job.

Jobs run one at a time on a single background worker, matching a single
shared GPU slot. Uploads, job state, and finished transcripts persist on disk
under `JOB_DATA_DIR` so the API survives restarts; model weights persist
under `HF_HOME` so they are downloaded once.

There is no cleanup/rewrite pass (e.g. via a local LLM) in this release —
only the raw Whisper transcript, grouped into speaker turns.

## Requirements

- Python 3.11
- [`uv`](https://docs.astral.sh/uv/)
- FFmpeg
- An NVIDIA GPU (CUDA 12.x) for any real workload; CPU works for tests only
- A Hugging Face read token with the Community-1 conditions accepted

## Configuration

Copy `.env.example` to `.env` and set `HF_TOKEN`. See that file for every
other setting (model choice, cache/job directories, device, CORS).

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```

Run the API locally (requires a CUDA GPU for anything beyond `/api/health`
and `/api/languages`):

```bash
uv run diarist-api
```

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

The image is CUDA-only (no CPU fallback) — see `Dockerfile` for the base
image. If you run multiple GPU workloads on one card, look into NVIDIA's
[time-slicing or MPS](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html)
features to share it between pods/containers.
