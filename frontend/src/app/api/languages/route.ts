import { NextResponse } from "next/server";

import { backendJson } from "@/lib/backend";
import type { Language } from "@/lib/types";

export async function GET() {
  const languages = await backendJson<Language[]>("/api/languages");
  return NextResponse.json(languages);
}
