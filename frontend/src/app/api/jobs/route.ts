import { NextRequest } from "next/server";

import { backendFetch, backendJson } from "@/lib/backend";
import { apiError, privateJson, requireApiSession, requireMutationOrigin } from "@/lib/api-security";
import type { Job } from "@/lib/types";

export async function GET() {
  try {
    await requireApiSession();
    const jobs = await backendJson<Job[]>("/api/jobs");
    return privateJson(jobs);
  } catch (error) {
    return apiError(error);
  }
}

export async function POST(request: NextRequest) {
  try {
    await requireApiSession();
    requireMutationOrigin(request);
    let incoming: FormData;
    try {
      incoming = await request.formData();
    } catch {
      return privateJson({ error: "Invalid upload form." }, 400);
    }
    const file = incoming.get("file");
    if (!(file instanceof File)) {
      return privateJson({ error: "A 'file' field is required." }, 400);
    }

    const outgoing = new FormData();
    outgoing.set("file", file, file.name);
    for (const field of ["language", "speakers", "initial_prompt"] as const) {
      const value = incoming.get(field);
      if (typeof value === "string" && value.length > 0) outgoing.set(field, value);
    }
    const response = await backendFetch("/api/jobs", { method: "POST", body: outgoing });
    const job = (await response.json()) as Job;
    return privateJson(job, 201);
  } catch (error) {
    return apiError(error);
  }
}
