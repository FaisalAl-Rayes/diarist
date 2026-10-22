import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse, type NextRequest, type NextFetchEvent } from "next/server";

// Defense in depth only; pages and every handler also authorize locally.
const clerkProxy = clerkMiddleware(async (auth, request) => {
  const path = request.nextUrl.pathname;
  if (/^\/sign-(in|up)(\/|$)/.test(path)) return;
  if (path === "/api" || path.startsWith("/api/")) {
    if (!(await auth()).isAuthenticated) {
      return NextResponse.json({ error: "Authentication required." }, {
        status: 401, headers: { "Cache-Control": "private, no-store" },
      });
    }
    return;
  }
  await auth.protect();
});

export default async function proxy(request: NextRequest, event: NextFetchEvent) {
  const response = await clerkProxy(request, event);
  const path = request.nextUrl.pathname;
  // Clerk can initiate a browser handshake before invoking our callback.
  // Even with Accept: text/html, API consumers must never receive that redirect.
  if (path === "/api" || path.startsWith("/api/")) {
    if (response && response.status >= 300 && response.status < 400) {
      return NextResponse.json({ error: "Authentication required." }, {
        status: 401, headers: { "Cache-Control": "private, no-store" },
      });
    }
    const result = response || NextResponse.next();
    result.headers.set("Cache-Control", "private, no-store");
    return result;
  }
  return response;
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
    "/__clerk/(.*)",
  ],
};
