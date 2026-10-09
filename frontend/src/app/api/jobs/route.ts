import { NextRequest, NextResponse } from "next/server";

import { BackendError, backendFetch, backendJson } from "@/lib/backend";
import type { Job } from "@/lib/types";

export async function GET() {
  const jobs = await backendJson<Job[]>("/api/jobs");
  return NextResponse.json(jobs);
}

export async function POST(request: NextRequest) {
  const incoming = await request.formData();
  const file = incoming.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "A 'file' field is required." }, { status: 400 });
  }

  const outgoing = new FormData();
  outgoing.set("file", file, file.name);
  for (const field of ["language", "speakers", "initial_prompt"] as const) {
    const value = incoming.get(field);
    if (typeof value === "string" && value.length > 0) {
      outgoing.set(field, value);
    }
  }

  try {
    const response = await backendFetch("/api/jobs", { method: "POST", body: outgoing });
    const job = (await response.json()) as Job;
    return NextResponse.json(job, { status: 201 });
  } catch (error) {
    if (error instanceof BackendError) {
      return NextResponse.json({ error: error.message }, { status: error.status });
    }
    throw error;
  }
}
