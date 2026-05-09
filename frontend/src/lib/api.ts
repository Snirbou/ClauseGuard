import { getAuthMode } from "@/lib/auth-service";
import { getAuthToken } from "@/lib/auth-utils";
import type {
  ContractResultsResponse,
  UploadResponse,
  UserContractSummary,
} from "@/types/contracts";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type FetchInput = Parameters<typeof fetch>[0];
type FetchInit = Parameters<typeof fetch>[1];

function mergeAuthHeaders(initHeaders?: HeadersInit): Headers {
  const headers = new Headers(initHeaders);
  const token = getAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

/**
 * Centralized fetch that injects `Authorization: Bearer <token>` when a JWT cookie exists.
 */
export async function authenticatedFetch(
  input: FetchInput,
  init: FetchInit = {},
): Promise<Response> {
  return fetch(input, {
    ...init,
    headers: mergeAuthHeaders(init.headers),
  });
}

export async function uploadContractFile(
  file: File,
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await authenticatedFetch(`${API_BASE_URL}/api/contracts/upload`, {
    method: "POST",
    body: formData,
  });

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
  const res = await authenticatedFetch(
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

/**
 * List saved contracts for the current user (client-side; uses JWT cookie).
 * In mock mode returns stub data; in live mode calls the backend.
 */
export async function fetchUserContracts(): Promise<UserContractSummary[]> {
  if (getAuthMode() === "mock") {
    return [
      {
        contract_id: "mock-1",
        filename: "Acme NDA.pdf",
        created_at: new Date(Date.now() - 86400000).toISOString(),
        clause_count: 18,
      },
      {
        contract_id: "mock-2",
        filename: "SaaS MSA v3.docx",
        created_at: new Date(Date.now() - 3600000).toISOString(),
        clause_count: 42,
      },
      {
        contract_id: "mock-3",
        filename: "Vendor SOW.pdf",
        created_at: new Date().toISOString(),
        clause_count: 7,
      },
    ];
  }

  const res = await authenticatedFetch(`${API_BASE_URL}/api/contracts`, {
    cache: "no-store",
  });
  if (!res.ok) return [];
  const json = (await res.json().catch(() => null)) as
    | UserContractSummary[]
    | null;
  return Array.isArray(json) ? json : [];
}
