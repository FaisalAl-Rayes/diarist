# Diarist — Frontend

Next.js (App Router) + [shadcn/ui](https://ui.shadcn.com) dashboard for the
transcription backend. Upload audio (click or drag-and-drop), pick a
language (or auto-detect) and optional speaker count, watch job status and
processing time, download the finished transcript as JSON or DOCX, and
delete jobs you no longer need. Light/dark/system theme, following the OS
by default.

The backend is never called directly from the browser. Every request goes
through this app's own route handlers (`src/app/api/**`), which forward to
`BACKEND_URL` server-side. This keeps the GPU backend off any public route
and avoids CORS entirely.

## Requirements

- Node.js 20+
- The backend running locally or reachable at `BACKEND_URL`

## Configuration

Copy `.env.example` to `.env.local` and set `BACKEND_URL`, the existing
application's Clerk publishable/secret keys, and `APP_ORIGIN` to the exact
browser origin (for example `http://localhost:3000`). Never commit real keys.
Use production Clerk keys and your HTTPS application origin for deployment.

`APP_ORIGIN` is required in production. Uploads and deletes require an exact
matching `Origin` header; missing, `null`, or cross-origin values are rejected.
Neither `Host` nor forwarded headers establish trust. When running on a
different development port, set `APP_ORIGIN` accordingly.

Pages and each API handler authenticate independently, with proxy protection
as a second layer. API failures are JSON (401 when signed out), not sign-in
redirects. The server forwards only the current Clerk session Bearer token
to the backend, never client identity headers or session cookies. Backend
requests and API responses (including errors/downloads) are not cached.
The backend must independently verify this token and scope jobs by its subject.
`/sign-in` and `/sign-up` and their nested authentication steps remain public.

## Development

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

```bash
npm run lint
npm test
npm run typecheck
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
docker build --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_public_key -t diarist-frontend .
```

Multi-stage build producing a `next start` standalone server. See
`Dockerfile`.
The public publishable key is embedded at build time. Provide `CLERK_SECRET_KEY`,
`BACKEND_URL`, and `APP_ORIGIN` only as runtime environment variables, never
secret build arguments. Environment files are excluded from the build context.
The container health check uses public `/sign-in`, not the protected homepage.

Unit and route tests mock Clerk's request context and the network; they exercise
resource-level guards without middleware, CSRF, token forwarding, sanitized
errors, private caching, and account controls. Real Clerk sign-in/sign-up,
sign-out, and two-user isolation still require an interactive browser and a
configured backend. Do not create test accounts without the app owner's approval.

## Dependency audit

`npm audit fix` applies compatible updates only. At integration time, npm still
reports nine high-severity affected packages from a single `braces` stack
exhaustion advisory (GHSA-vfj7-8cjw-p6xm), through the shadcn CLI and Next.js
ESLint dependency chains. The registry has no patched `braces` release yet;
npm suggests incompatible major downgrades of shadcn and eslint-config-next.
Those downgrades and `--force` were deliberately not used. Re-run `npm audit`
when upstream fixes become available. Do not process untrusted glob patterns
with these development/build tools.
