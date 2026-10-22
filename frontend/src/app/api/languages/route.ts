import { apiError, privateJson, requireApiSession } from "@/lib/api-security";
import { backendJson } from "@/lib/backend";
import type { Language } from "@/lib/types";

export async function GET() {
  try {
    await requireApiSession();
    const languages = await backendJson<Language[]>("/api/languages");
    return privateJson(languages);
  } catch (error) {
    return apiError(error);
  }
}
