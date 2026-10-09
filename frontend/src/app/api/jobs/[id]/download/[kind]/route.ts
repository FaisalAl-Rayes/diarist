import { NextResponse } from "next/server";

import { BackendError, backendFetch } from "@/lib/backend";

const CONTENT_TYPES: Record<string, string> = {
  json: "application/json",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; kind: string }> },
) {
  const { id, kind } = await params;
  if (kind !== "json" && kind !== "docx") {
    return NextResponse.json({ error: "Unknown download kind." }, { status: 400 });
  }
  try {
    const response = await backendFetch(
      `/api/jobs/${encodeURIComponent(id)}/download/${kind}`,
    );
    const body = await response.arrayBuffer();
    return new NextResponse(body, {
      headers: {
        "Content-Type": CONTENT_TYPES[kind],
        "Content-Disposition": `attachment; filename="${id}-transcript.${kind}"`,
      },
    });
  } catch (error) {
    if (error instanceof BackendError) {
      return NextResponse.json({ error: error.message }, { status: error.status });
    }
    throw error;
  }
}
