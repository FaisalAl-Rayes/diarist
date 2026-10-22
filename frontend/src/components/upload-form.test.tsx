import { beforeEach, expect, it, vi } from "vitest";
import { isValidElement, type ReactNode } from "react";

// Exercise the mount effect and subsequent render without a DOM or network.
const hooks = vi.hoisted(() => ({
  states: [] as unknown[],
  cursor: 0,
  effect: undefined as (() => void) | undefined,
}));
vi.mock("react", async (importOriginal) => ({
  ...await importOriginal<typeof import("react")>(),
  useState: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.states)) hooks.states[index] = initial;
    return [hooks.states[index], (value: unknown) => { hooks.states[index] = value; }];
  },
  useEffect: (effect: () => void) => { hooks.effect = effect; },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));

import { Select, SelectItem } from "@/components/ui/select";
import { UploadForm } from "./upload-form";

function languagePicker() {
  hooks.cursor = 0;
  const options: { code: unknown; name: ReactNode }[] = [];
  let selected: unknown;
  function visit(node: ReactNode) {
    if (Array.isArray(node)) return node.forEach(visit);
    if (!isValidElement<{ children?: ReactNode; value?: unknown }>(node)) return;
    if (node.type === Select) selected = node.props.value;
    if (node.type === SelectItem) options.push({ code: node.props.value, name: node.props.children });
    visit(node.props.children);
  }
  visit(UploadForm());
  return { selected, options };
}

beforeEach(() => {
  hooks.states = [];
  hooks.cursor = 0;
  hooks.effect = undefined;
  vi.stubGlobal("fetch", vi.fn());
});

it.each([
  ["401 error", 401, { error: "Authentication required." }],
  ["502 error", 502, { error: "The transcription service is unavailable." }],
  ["401 with an array", 401, [{ code: "fr", name: "French" }]],
  ["502 with an array", 502, [{ code: "fr", name: "French" }]],
  ["200 error object", 200, { error: "Unexpected payload" }],
  ["200 null", 200, null],
  ["200 invalid entry", 200, [{ code: "en", name: "English" }, null]],
  ["200 missing name", 200, [{ code: "en" }]],
  ["200 non-string code", 200, [{ code: 42, name: "English" }]],
  ["200 non-string name", 200, [{ code: "en", name: 42 }]],
])("keeps the English/auto fallback for %s", async (_name, status, payload) => {
  vi.mocked(fetch).mockResolvedValue(Response.json(payload, { status }));
  const fallback = languagePicker();
  hooks.effect!();
  await new Promise<void>((resolve) => setImmediate(resolve));
  expect(fetch).toHaveBeenCalledExactlyOnceWith("/api/languages");
  expect(languagePicker()).toEqual(fallback);
  expect(fallback).toEqual({ selected: "en", options: [
    { code: "en", name: "English" },
    { code: "auto", name: "Detect automatically" },
  ] });
});

it("loads a valid language array", async () => {
  vi.mocked(fetch).mockResolvedValue(Response.json([{ code: "fr", name: "French" }]));
  languagePicker();
  hooks.effect!();
  await new Promise<void>((resolve) => setImmediate(resolve));
  expect(languagePicker().options).toEqual([{ code: "fr", name: "French" }]);
});
