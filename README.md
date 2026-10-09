<img src="frontend/public/logo.svg" alt="Diarist" width="56" height="56" />

# Diarist

A self-hosted, local-first multi-speaker transcription web app. Upload a
recording and get back a word-timestamped, speaker-labeled transcript (JSON
and DOCX), in any language [Whisper large-v3](https://github.com/openai/whisper)
supports (English by default), or let it auto-detect the language.

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CUDA or CPU)
  or [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)
  (Apple Silicon/Metal, native only) for transcription -- auto-detected, see
  [Hardware/backends](#hardwarebackends) below.
- [pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
  for speaker diarization.
- No cloud calls beyond the one-time Hugging Face model download; audio and
  transcripts never leave your own infrastructure.
- No cleanup/rewrite pass (e.g. via a local LLM) yet -- only the raw Whisper
  transcript, grouped into speaker turns.

## Requirements

- Docker and Docker Compose (or see [Development](#development-without-docker)
  to run natively instead).
- A Hugging Face read token with the
  [Community-1 conditions](https://huggingface.co/pyannote/speaker-diarization-community-1)
  accepted (diarization only; Whisper itself needs no token).

## Quickstart

```bash
cp .env.example .env
# edit .env and set HF_TOKEN

docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). The first job will be
slow while Whisper and pyannote download their model weights into the
`model-cache` volume; subsequent jobs reuse the cache.

This works on any Docker host -- Mac, Linux, Windows/WSL2 -- but runs on
**CPU only**. See the next section for faster options.

## Hardware/backends

Diarist auto-detects what it's running on and picks accordingly, but the
options differ by *how* you run it, not just *what hardware* you have:

| How you run it | Transcription | Diarization |
| --- | --- | --- |
| `docker compose up` (any host) | faster-whisper, CPU | CPU |
| `docker compose up` + `docker-compose.gpu.yaml` (Linux + NVIDIA GPU) | faster-whisper, CUDA | CUDA |
| Native, Apple Silicon (`uv run`, not Docker) | mlx-whisper, Metal | MPS (Metal) |

**Docker can never use MLX, on any host**, including Apple Silicon Macs:
Docker Desktop runs containers inside a Linux VM with no Metal passthrough.
This is a virtualization boundary, not a configuration option. If you want
real Apple Silicon acceleration, run the backend natively:

```bash
cd backend
uv sync --extra mlx
WHISPER_BACKEND=mlx uv run diarist-api
```

For an NVIDIA GPU host, layer the GPU override onto Compose so the
container actually gets the device (without it, the backend falls back to
CPU even if the host has a GPU, because Docker never exposed it):

```bash
docker compose -f docker-compose.yaml -f docker-compose.gpu.yaml up --build
```

Every device/backend choice is also overridable via environment variables
(`WHISPER_BACKEND`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`,
`DIARIZATION_DEVICE`) if auto-detection picks the wrong thing -- see
`backend/.env.example`.

## Layout

```text
backend/   FastAPI job API: faster-whisper/mlx-whisper + pyannote, one job at a time
frontend/  Next.js + shadcn/ui dashboard: upload, job status, downloads
```

Each has its own `README.md`, `Dockerfile`, and `.env.example`. The frontend
never calls the backend directly from the browser, and
`docker-compose.yaml` doesn't publish the backend's port to the host -- see
`frontend/README.md` for why, and `backend/README.md` for the API surface.

## Development (without Docker)

```bash
cd backend && uv sync && uv run pytest
cd frontend && npm install && npm run dev
```

Both services need to run together for a full local test: start the
backend first (`uv run diarist-api`), then the frontend with `BACKEND_URL`
pointing at it. On Apple Silicon, add `uv sync --extra mlx` and set
`WHISPER_BACKEND=mlx` for real transcription speed (see
[Hardware/backends](#hardwarebackends)); otherwise expect CPU speed.

## Deployment

Both images are built and pushed to GHCR by
[`.github/workflows/build-images.yml`](.github/workflows/build-images.yml) on
every push to `main` that touches `backend/` or `frontend/`.

`docker-compose.yaml` (plus the optional `docker-compose.gpu.yaml`) at the
repo root is the reference deployment; adapt it to Kubernetes, Nomad, etc.
as needed for your own infrastructure. If you run more than one GPU
workload on a single card, look into NVIDIA's
[time-slicing or MPS](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html)
to share it.

## License

[MIT](LICENSE).
