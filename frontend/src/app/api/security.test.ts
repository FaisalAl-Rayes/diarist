import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
vi.mock("server-only", () => ({}));
const { auth, getToken } = vi.hoisted(() => ({ auth: vi.fn(), getToken: vi.fn() }));
vi.mock("@clerk/nextjs/server", () => ({ auth }));
import { GET as jobs, POST as upload } from "./jobs/route";
import { GET as languages } from "./languages/route";
import { GET as job, DELETE as remove } from "./jobs/[id]/route";
import { GET as download } from "./jobs/[id]/download/[kind]/route";

const context = { params: Promise.resolve({ id: "job_1", kind: "json" }) };
const request = (origin?: string) => new NextRequest("http://localhost:3000/api/jobs", {
  method: "POST", headers: origin ? { origin } : {},
});
const handlers = [
  ["jobs", () => jobs()], ["languages", () => languages()],
  ["job", () => job(request(), context)], ["delete", () => remove(request(), context)],
  ["download", () => download(request(), context)], ["upload", () => upload(request())],
] as const;

beforeEach(() => {
  vi.stubEnv("APP_ORIGIN", "https://diarist.example");
  auth.mockResolvedValue({ isAuthenticated: false, getToken });
  getToken.mockResolvedValue("session-token");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]")));
});

describe("resource-local protection (without middleware)", () => {
  it.each(handlers)("%s rejects a pending session with a userId before retrieving a token", async (_name, handler) => {
    auth.mockResolvedValue({ isAuthenticated: false, sessionStatus: "pending", userId: "user_a", getToken });
    expect((await handler()).status).toBe(401);
    expect(getToken).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each(handlers)("%s returns private 401 JSON, never a redirect", async (_name, handler) => {
    const response = await handler();
    expect(response.status).toBe(401);
    expect(response.headers.get("content-type")).toContain("application/json");
    expect(response.headers.get("location")).toBeNull();
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(await response.json()).toEqual({ error: "Authentication required." });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("authenticates before parsing an upload", async () => {
    const req = request();
    const parser = vi.spyOn(req, "formData");
    await upload(req);
    expect(parser).not.toHaveBeenCalled();
  });
});

describe("mutation CSRF protection", () => {
  beforeEach(() => auth.mockResolvedValue({ isAuthenticated: true, getToken }));
  it.each([undefined, "null", "https://attacker.example", "https://diarist.example.evil", "http://diarist.example"])("rejects Origin %s before parsing", async (origin) => {
    const req = request(origin);
    const parser = vi.spyOn(req, "formData");
    expect((await upload(req)).status).toBe(403);
    expect((await remove(req, context)).status).toBe(403);
    expect(parser).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("does not trust Host or forwarded headers", async () => {
    const req = request("https://attacker.example");
    req.headers.set("host", "attacker.example");
    req.headers.set("x-forwarded-host", "attacker.example");
    expect((await remove(req, context)).status).toBe(403);
  });
  it("allows the configured exact Origin and keeps 204 private", async () => {
    const response = await remove(request("https://diarist.example"), context);
    expect(response.status).toBe(204);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
  });
  it("fails closed when the production origin is not configured", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("APP_ORIGIN", "");
    const response = await remove(request("https://diarist.example"), context);
    expect(response.status).toBe(503);
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("authenticated responses", () => {
  beforeEach(() => auth.mockResolvedValue({ isAuthenticated: true, getToken }));
  it.each(handlers.slice(0, 3))("%s successes are private", async (_name, handler) => {
    expect((await handler()).headers.get("cache-control")).toBe("private, no-store");
  });
  it("downloads are private and preserve only deliberate headers", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("transcript", { headers: { "cache-control": "public", "set-cookie": "secret" } }));
    const response = await download(request(), context);
    expect(await response.text()).toBe("transcript");
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(response.headers.get("content-disposition")).toContain("attachment");
  });
  it.each(handlers.slice(0, 3))("%s backend failures are sanitized JSON", async (_name, handler) => {
    vi.mocked(fetch).mockResolvedValue(new Response("secret token", { status: 500 }));
    const response = await handler();
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ error: "The transcription service is unavailable." });
  });
  it("invalid upload responses are private", async () => {
    const req = request("https://diarist.example");
    vi.spyOn(req, "formData").mockResolvedValue(new FormData());
    const response = await upload(req);
    expect(response.status).toBe(400);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
  });
  it("forwards only allowed multipart fields with the server token", async () => {
    const form = new FormData();
    form.set("file", new File(["audio"], "recording.wav", { type: "audio/wav" }));
    form.set("language", "en");
    form.set("speakers", "2");
    form.set("initial_prompt", "Meeting");
    form.set("user_id", "attacker");
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ id: "new_job" })));
    const req = new NextRequest("http://localhost:3000/api/jobs", {
      method: "POST", body: form, headers: { origin: "https://diarist.example", "x-user-id": "attacker" },
    });
    const response = await upload(req);
    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({ id: "new_job" });
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    const options = vi.mocked(fetch).mock.calls[0][1]!;
    const outgoing = options.body as FormData;
    expect([...outgoing.keys()].sort()).toEqual(["file", "initial_prompt", "language", "speakers"]);
    expect((outgoing.get("file") as File).name).toBe("recording.wav");
    expect(new Headers(options.headers).get("authorization")).toBe("Bearer session-token");
    expect(new Headers(options.headers).has("x-user-id")).toBe(false);
  });
});
