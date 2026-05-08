import type {
  ContractResultsResponse,
  UploadResponse,
} from "@/types/contracts";

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
    contract_id: null,
    parsed_clauses: [],
    detail: "Invalid response from backend.",
  };
}

export async function fetchContractResults(
  contractId: string,
): Promise<ContractResultsResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/contracts/${contractId}/results`,
    { cache: "no-store" },
  );

  const json = (await res.json().catch(() => null)) as
    | ContractResultsResponse
    | null;
  if (json && typeof json === "object") return json;

  return {
    status: "error",
    contract_id: contractId,
    filename: "",
    clauses: [],
    disclaimer: "",
    detail: `Results fetch failed (${res.status}).`,
  };
}
