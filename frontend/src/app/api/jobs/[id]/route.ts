import { NextResponse } from "next/server";

import { backendFetch, backendJson } from "@/lib/backend";
import { apiError, PRIVATE_HEADERS, privateJson, requireApiSession, requireMutationOrigin } from "@/lib/api-security";
import type { Job } from "@/lib/types";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    await requireApiSession();
    const { id } = await params;
    const job = await backendJson<Job>(`/api/jobs/${encodeURIComponent(id)}`);
    return privateJson(job);
  } catch (error) {
    return apiError(error);
  }
}

export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    await requireApiSession();
    requireMutationOrigin(request);
    const { id } = await params;
    await backendFetch(`/api/jobs/${encodeURIComponent(id)}`, { method: "DELETE" });
    return new NextResponse(null, { status: 204, headers: PRIVATE_HEADERS });
  } catch (error) {
    return apiError(error);
  }
}
