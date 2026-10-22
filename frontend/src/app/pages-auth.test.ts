import { beforeEach, expect, it, vi } from "vitest";
vi.mock("server-only", () => ({}));
const { protect, backendJson } = vi.hoisted(() => ({ protect: vi.fn(), backendJson: vi.fn() }));
vi.mock("@clerk/nextjs/server", () => ({ auth: { protect } }));
vi.mock("@/lib/backend", () => ({ backendJson, BackendError: class extends Error {} }));
vi.mock("@/components/jobs-table", () => ({ JobsTable: () => null }));
vi.mock("@/components/upload-form", () => ({ UploadForm: () => null }));
vi.mock("@/components/job-detail", () => ({ JobDetail: () => null }));
vi.mock("@/components/mode-toggle", () => ({ ModeToggle: () => null }));
vi.mock("@/components/account-controls", () => ({ AccountControls: () => null }));
import HomePage from "./page";
import JobPage from "./jobs/[id]/page";

beforeEach(() => backendJson.mockResolvedValue([]));
it.each([
  ["homepage", () => HomePage()],
  ["job page", () => JobPage({ params: Promise.resolve({ id: "job_1" }) })],
] as const)("%s protects before fetching; redirects cannot be swallowed", async (_name, page) => {
  const redirect = new Error("NEXT_REDIRECT");
  protect.mockRejectedValue(redirect);
  await expect(page()).rejects.toBe(redirect);
  expect(backendJson).not.toHaveBeenCalled();
});
