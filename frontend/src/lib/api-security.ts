import "server-only";
import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { BackendError } from "@/lib/backend";

export const PRIVATE_HEADERS = { "Cache-Control": "private, no-store" };

/** Resource-local guard: never use auth.protect() here (it can redirect to HTML). */
export async function requireApiSession() {
  const session = await auth();
  if (!session.isAuthenticated) throw new BackendError("Authentication required.", 401);
}

/** Cookie-authenticated mutations require an exact, explicitly trusted Origin. */
export function requireMutationOrigin(request: Request) {
  const configured = process.env.APP_ORIGIN ?? (process.env.NODE_ENV === "development" ? "http://localhost:3000" : "");
  let expected: string;
  try {
    const url = new URL(configured);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.pathname !== "/" || url.search || url.hash) throw new Error();
    expected = url.origin;
  } catch {
    throw new BackendError("Application origin is not configured.", 503);
  }
  if (request.headers.get("origin") !== expected) {
    throw new BackendError("Untrusted request origin.", 403);
  }
}

export function privateJson(body: unknown, status = 200) {
  return NextResponse.json(body, { status, headers: PRIVATE_HEADERS });
}

export function apiError(error: unknown) {
  if (error instanceof BackendError) return privateJson({ error: error.message }, error.status);
  return privateJson({ error: "Unable to complete the request." }, 500);
}
