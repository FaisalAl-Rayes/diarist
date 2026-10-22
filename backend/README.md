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

Use `.env.example` as the configuration reference and set `HF_TOKEN`,
`CLERK_ISSUER_URL`, and `CLERK_AUTHORIZED_PARTIES` in the process environment
(or pass an env file to your container). The local CLI does not load `.env`
automatically. See the example for backend/model choice, directories, devices,
and CORS. Clerk configuration is public; this backend needs **no Clerk secret key**.

Example local Clerk configuration (replace the issuer with your own instance):

```bash
export CLERK_ISSUER_URL=https://your-instance.clerk.accounts.dev
export CLERK_AUTHORIZED_PARTIES=http://localhost:3000
```

For deployment, set the actual Clerk instance's HTTPS issuer origin (no trailing
slash) and a comma-separated list of exact frontend origins. Wildcards and paths
are not accepted. Do not retain localhost or the development issuer in production.
Supply both values as **runtime environment variables** to the API container;
neither needs an image build argument or a secret key.

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

Every `/api/jobs` endpoint requires `Authorization: Bearer <session JWT>`.
The Next.js server forwards the ordinary Clerk session token; the API independently
verifies its RS256 signature using only the configured issuer's
`/.well-known/jwks.json`. It requires and validates `exp`, `nbf`, `iat`, `iss`,
`sub`, `sid`, and an exact allowlisted `azp` (tokens without `azp` are rejected).
If the `sts` session-status claim is present, it must be exactly `"active"`;
`"pending"`, unknown statuses, and malformed values are rejected with 401. Omitted
`sts` remains accepted for ordinary/legacy session tokens, subject to every other
signature and claim check.
Identity headers and submitted owner/user fields are never trusted. Health and
languages remain public. Missing/invalid tokens return 401; missing/invalid auth
configuration or unavailable JWKS return 503. Private responses, including
downloads and errors, are marked `Cache-Control: private, no-store`.

Ownership is persisted from the verified subject. Lists only include that user's
jobs, and foreign, missing, or unsafe job paths produce the same 404. Legacy
records with no owner are **hidden and not resumed**, never assigned to a new
account. They remain on disk for an explicit administrator migration or removal.

Deleting an active job immediately hides it and persists a deletion marker.
Physical removal waits until its transcription engine returns, so an in-flight
worker cannot recreate deleted outputs. Restart completes marked deletions before
resuming owned jobs. The manager initializes lazily on the first authenticated job
request, without loading models during import.

Downloads authorize the owner and open the output under the same manager lock
used by deletion, then stream the already-open handle in bounded chunks. A
concurrent deletion can remove the job while an authorized download finishes;
the handle closes on completion, disconnect, or failure. If the output disappears
before opening, the API returns the same private, no-store 404 as a missing job.

Use **one API process/replica per job directory**; the queue, locking, and worker
coordination are in-process, not distributed. Keep `JOB_DATA_DIR` writable only by
the service account (including its backups), use HTTPS, and restrict backend
network access. Path/symlink checks do not replace host filesystem access controls.

- `GET /api/health`
- `GET /api/languages` — Whisper-supported language codes for the UI's picker
- `POST /api/jobs` — multipart upload: `file`, optional `language` (default
  `en`; pass `auto` for language auto-detection), `speakers`, `initial_prompt`
- `GET /api/jobs` — most recent first
- `GET /api/jobs/{id}` — includes `started_at`/`completed_at` (both `null`
  until processing begins/ends; subtract them for processing time)
- `DELETE /api/jobs/{id}` — deletes the job's input, output, and state
- `GET /api/jobs/{id}/download/json`
- `GET /api/jobs/{id}/download/docx`

The backend test suite uses temporary storage, a fake transcription engine, and
locally generated RSA keys/JWKS. It covers anonymous requests, two-user isolation,
claim/signature failures, forged identity fields, owner persistence/recovery,
legacy records, unsafe paths, and deletion races without model downloads or a live
Clerk login. These tests do not replace a deployed frontend sign-in smoke test.

Verification follows Clerk's official [manual JWT verification guide](https://clerk.com/docs/guides/sessions/manual-jwt-verification)
and [session token claim reference](https://clerk.com/docs/guides/sessions/session-tokens).
Diarist intentionally requires `azp` even though Clerk permits some clients to omit it.

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
