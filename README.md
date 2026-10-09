# Diarist

A self-hosted, local-first multi-speaker transcription web app. Upload a
recording and get back a word-timestamped, speaker-labeled transcript (JSON
and DOCX), in any language [Whisper large-v3](https://github.com/openai/whisper)
supports (English by default), or let it auto-detect the language.

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CUDA) for
  transcription.
- [pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
  for speaker diarization.
- No cloud calls beyond the one-time Hugging Face model download; audio and
  transcripts never leave your own infrastructure.
- No cleanup/rewrite pass (e.g. via a local LLM) yet -- only the raw Whisper
  transcript, grouped into speaker turns.

## Requirements

- An NVIDIA GPU (CUDA 12.x) and the
  [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  on the Docker host -- this is GPU-only, there is no CPU inference path for
  real workloads.
- A Hugging Face read token with the
  [Community-1 conditions](https://huggingface.co/pyannote/speaker-diarization-community-1)
  accepted (diarization only; Whisper itself needs no token).
- Docker and Docker Compose.

## Quickstart

```bash
cp .env.example .env
# edit .env and set HF_TOKEN

docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). The first job will be
slow while Whisper and pyannote download their model weights into the
`model-cache` volume; subsequent jobs reuse the cache.

## Layout

```text
backend/   FastAPI job API: faster-whisper + pyannote, one GPU job at a time
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

Both services need to run together for a full local test: start the backend
first (`uv run diarist-api`, requires a CUDA GPU for actual transcription),
then the frontend with `BACKEND_URL` pointing at it.

## Deployment

Both images are built and pushed to GHCR by
[`.github/workflows/build-images.yml`](.github/workflows/build-images.yml) on
every push to `main` that touches `backend/` or `frontend/`.

`docker-compose.yaml` at the repo root is the reference deployment; adapt it
to Kubernetes, Nomad, etc. as needed for your own infrastructure. If you run
more than one GPU workload on a single card, look into NVIDIA's
[time-slicing or MPS](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html)
to share it.

## License

[MIT](LICENSE).
