# Diarist — Frontend

Next.js (App Router) + [shadcn/ui](https://ui.shadcn.com) dashboard for the
transcription backend. Upload audio, pick a language (or auto-detect) and
optional speaker count, watch job status, and download the finished
transcript as JSON or DOCX.

The backend is never called directly from the browser. Every request goes
through this app's own route handlers (`src/app/api/**`), which forward to
`BACKEND_URL` server-side. This keeps the GPU backend off any public route
and avoids CORS entirely.

## Requirements

- Node.js 20+
- The backend running locally or reachable at `BACKEND_URL`

## Configuration

Copy `.env.example` to `.env.local` and set `BACKEND_URL`.

## Development

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

```bash
npm run lint
npm run build
```

## Structure

- `src/app/page.tsx` — upload form + job list (polls every 4s)
- `src/app/jobs/[id]/page.tsx` — job detail, polls while queued/processing
- `src/app/api/**` — server-side proxy to the backend
- `src/components/ui/**` — shadcn/ui components (do not hand-edit; use
  `npx shadcn@latest add/diff` to update)

## Container image

```bash
docker build -t diarist-frontend .
```

Multi-stage build producing a `next start` standalone server. See
`Dockerfile`.
