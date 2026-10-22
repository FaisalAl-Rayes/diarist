import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
const { auth, getToken } = vi.hoisted(() => ({ auth: vi.fn(), getToken: vi.fn() }));
vi.mock("@clerk/nextjs/server", () => ({ auth }));
import { backendFetch } from "./backend";

describe("authenticated backend transport", () => {
  beforeEach(() => {
    auth.mockResolvedValue({ isAuthenticated: true, userId: "user_a", getToken });
    getToken.mockResolvedValue("session-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));
  });

  it("replaces caller authorization and drops identity headers and cookies", async () => {
    await backendFetch("/api/jobs", { headers: {
      Authorization: "Bearer attacker", "X-User-Id": "user_b", "X-Clerk-User-Id": "user_b",
      Cookie: "__session=attacker", "X-Forwarded-User": "user_b", "Content-Type": "application/json",
    }, cache: "force-cache" });
    const options = vi.mocked(fetch).mock.calls[0][1]!;
    const headers = new Headers(options.headers);
    expect(headers.get("authorization")).toBe("Bearer session-token");
    expect([...headers.keys()].sort()).toEqual(["authorization", "content-type"]);
    expect(options.cache).toBe("no-store");
    expect(options.redirect).toBe("error");
    expect(getToken).toHaveBeenCalledWith();
  });

  it("fails closed without a current session token", async () => {
    getToken.mockResolvedValue(null);
    await expect(backendFetch("/api/jobs")).rejects.toMatchObject({ status: 401 });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects a pending session with a userId before token retrieval", async () => {
    auth.mockResolvedValue({ isAuthenticated: false, sessionStatus: "pending", userId: "user_a", getToken });
    await expect(backendFetch("/api/jobs")).rejects.toMatchObject({ status: 401 });
    expect(getToken).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not leak backend errors", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("secret filesystem and token", { status: 500 }));
    await expect(backendFetch("/api/jobs")).rejects.toMatchObject({ status: 502, message: "The transcription service is unavailable." });
  });
});
