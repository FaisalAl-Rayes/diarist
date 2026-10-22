import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";
import { apiError, PRIVATE_HEADERS, privateJson, requireApiSession } from "@/lib/api-security";

const CONTENT_TYPES: Record<string, string> = {
  json: "application/json",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; kind: string }> },
) {
  try {
    await requireApiSession();
    const { id, kind } = await params;
    if (kind !== "json" && kind !== "docx") {
      return privateJson({ error: "Unknown download kind." }, 400);
    }
    const response = await backendFetch(
      `/api/jobs/${encodeURIComponent(id)}/download/${kind}`,
    );
    const body = await response.arrayBuffer();
    return new NextResponse(body, {
      headers: {
        ...PRIVATE_HEADERS,
        "Content-Type": CONTENT_TYPES[kind],
        "Content-Disposition": `attachment; filename="${id.replace(/[^a-zA-Z0-9_-]/g, "_")}-transcript.${kind}"`,
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (error) {
    return apiError(error);
  }
}
