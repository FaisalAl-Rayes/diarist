import "server-only";

/**
 * All calls to the transcription backend go through Next.js route handlers
 * (src/app/api/**) so the backend API never needs a public route or CORS
 * configuration — only this frontend talks to it, over the private network
 * between containers (e.g. the docker-compose network, or a Kubernetes
 * Service with no Ingress/Route of its own).
 */
const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class BackendError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "BackendError";
  }
}

export async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${BACKEND_URL}${path}`, {
    ...init,
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new BackendError(body || response.statusText, response.status);
  }
  return response;
}

export async function backendJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await backendFetch(path, init);
  return (await response.json()) as T;
}
