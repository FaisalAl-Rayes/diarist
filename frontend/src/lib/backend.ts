import "server-only";
import { auth } from "@clerk/nextjs/server";

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
  const session = await auth();
  const token = session.isAuthenticated ? await session.getToken() : null;
  if (!token) throw new BackendError("Authentication required.", 401);

  // Allow only payload negotiation headers, never client-supplied identity.
  const supplied = new Headers(init?.headers);
  const headers = new Headers();
  for (const name of ["content-type", "accept"]) {
    const value = supplied.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}${path}`, {
      ...init,
      headers,
      cache: "no-store",
      redirect: "error",
    });
  } catch {
    throw new BackendError("The transcription service is unavailable.", 502);
  }
  if (!response.ok) {
    const messages: Record<number, string> = {
      400: "Invalid request.", 401: "Authentication required.",
      403: "Access denied.", 404: "Not found.", 409: "The job cannot be changed right now.",
      413: "The uploaded file is too large.", 415: "Unsupported audio format.",
      422: "Invalid transcription settings.", 429: "Too many requests. Try again later.",
    };
    const message = messages[response.status];
    throw new BackendError(message ?? "The transcription service is unavailable.", message ? response.status : 502);
  }
  return response;
}

export async function backendJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await backendFetch(path, init);
  return (await response.json()) as T;
}
