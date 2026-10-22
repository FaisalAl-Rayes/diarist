import { beforeEach, expect, it, vi } from "vitest";
import { NextRequest, NextResponse, type NextFetchEvent } from "next/server";
const { middleware, auth, protect, clerkHandler } = vi.hoisted(() => ({ middleware: vi.fn(), auth: vi.fn(), protect: vi.fn(), clerkHandler: vi.fn() }));
vi.mock("@clerk/nextjs/server", () => ({ clerkMiddleware: middleware }));

beforeEach(() => {
  auth.mockResolvedValue({ isAuthenticated: false });
  Object.assign(auth, { protect });
  middleware.mockReturnValue(clerkHandler);
});
async function run(path: string) {
  vi.resetModules();
  await import("./proxy");
  return middleware.mock.calls[0][0](auth, new NextRequest(`http://localhost:3000${path}`));
}
it("rejects API access with JSON in middleware too", async () => {
  const response = await run("/api/jobs");
  expect(response.status).toBe(401);
  expect(await response.json()).toEqual({ error: "Authentication required." });
  expect(response.headers.get("cache-control")).toBe("private, no-store");
  expect(protect).not.toHaveBeenCalled();
});
it.each(["/sign-in", "/sign-in/factor-one", "/sign-up", "/sign-up/verify-email-address"])("keeps %s public", async (path) => {
  await run(path);
  expect(auth).not.toHaveBeenCalled();
  expect(protect).not.toHaveBeenCalled();
});
it("protects private pages", async () => {
  await run("/");
  expect(protect).toHaveBeenCalled();
});

it("converts Clerk's pre-handler HTML handshake redirect to private API 401 JSON", async () => {
  vi.resetModules();
  clerkHandler.mockResolvedValue(NextResponse.redirect("https://clerk.example/v1/client/handshake"));
  const { default: proxy } = await import("./proxy");
  const response = await proxy(new NextRequest("http://localhost:3000/api/jobs", { headers: { accept: "text/html" } }), {} as NextFetchEvent);
  expect(response?.status).toBe(401);
  expect(response?.headers.get("cache-control")).toBe("private, no-store");
  expect(response?.headers.get("location")).toBeNull();
  expect(await response?.json()).toEqual({ error: "Authentication required." });
});

it("marks all API middleware responses private, including automatic method responses", async () => {
  vi.resetModules();
  clerkHandler.mockResolvedValue(NextResponse.next());
  const { default: proxy } = await import("./proxy");
  const response = await proxy(new NextRequest("http://localhost:3000/api/jobs", { method: "OPTIONS" }), {} as NextFetchEvent);
  expect(response?.headers.get("cache-control")).toBe("private, no-store");
});
