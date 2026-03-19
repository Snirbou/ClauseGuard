import type { UploadResponse } from "@/types/contracts";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function uploadContractFile(
  file: File,
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/api/contracts/upload`, {
    method: "POST",
    body: formData,
  });

  // Backend should always return JSON, but keep a safe fallback.
  const json = (await res.json().catch(() => null)) as UploadResponse | null;
  if (json && typeof json === "object") return json;

  return {
    status: "error",
    filename: file.name,
    parsed_clauses: [],
    detail: "Invalid response from backend.",
  };
}

