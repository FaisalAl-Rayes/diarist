import { NextResponse } from "next/server";

import { BackendError, backendFetch, backendJson } from "@/lib/backend";
import type { Job } from "@/lib/types";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  try {
    const job = await backendJson<Job>(`/api/jobs/${encodeURIComponent(id)}`);
    return NextResponse.json(job);
  } catch (error) {
    if (error instanceof BackendError) {
      return NextResponse.json({ error: error.message }, { status: error.status });
    }
    throw error;
  }
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  try {
    await backendFetch(`/api/jobs/${encodeURIComponent(id)}`, { method: "DELETE" });
    return new NextResponse(null, { status: 204 });
  } catch (error) {
    if (error instanceof BackendError) {
      return NextResponse.json({ error: error.message }, { status: error.status });
    }
    throw error;
  }
}
