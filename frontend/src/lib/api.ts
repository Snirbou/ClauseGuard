import {
  MAX_UPLOAD_BYTES,
  type AnalysisRun,
  type AnalysisRunResponse,
  type AnalyzeAcceptedResponse,
  type ApiErrorResponse,
  type ContractDetail,
  type ContractListResponse,
  type ContractSummary,
  type DeleteResponse,
  type HealthResponse,
  type MetricsResponse,
  type UploadResponse,
  type UserInfo,
} from "@/types/contracts";

// Default: same-origin — /api/* is rewritten to the backend by
// next.config.ts, which lets the httpOnly session cookie ride along on
// plain http in development. Point NEXT_PUBLIC_API_BASE_URL at the backend
// directly only for cookie-less setups.
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/**
 * An API call that failed. `status` is 0 when the request never reached the
 * backend at all, which is by far the most common case in local development
 * (backend not running) and deserves its own message.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

const NETWORK_ERROR_MESSAGE =
  "Could not reach the ClauseGuard API. Make sure the backend is running on " +
  `${API_BASE_URL}.`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      // Always hit the backend; contract data changes as soon as analysis runs.
      cache: "no-store",
      ...init,
    });
  } catch {
    throw new ApiError(NETWORK_ERROR_MESSAGE, 0);
  }

  const body: unknown =
    res.status === 204 ? undefined : await res.json().catch(() => null);

  if (!res.ok) {
    const detail = (body as ApiErrorResponse | null)?.detail;
    throw new ApiError(
      detail ?? `Request failed with status ${res.status}.`,
      res.status,
    );
  }

  if (res.status !== 204 && body === null) {
    throw new ApiError("The backend returned a response we could not read.", res.status);
  }

  return body as T;
}

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------

/**
 * Upload a contract PDF.
 *
 * Unlike the other helpers this never throws for an API-level failure: the
 * upload endpoint returns a structured error envelope that the dropzone
 * renders directly.
 */
export async function uploadContractFile(file: File): Promise<UploadResponse> {
  if (file.size > MAX_UPLOAD_BYTES) {
    return {
      status: "error",
      filename: file.name,
      contract_id: null,
      parsed_clauses: [],
      detail: `File is too large (${formatBytes(file.size)}). Maximum size is ${formatBytes(
        MAX_UPLOAD_BYTES,
      )}.`,
    };
  }

  if (file.size === 0) {
    return {
      status: "error",
      filename: file.name,
      contract_id: null,
      parsed_clauses: [],
      detail: "This file is empty.",
    };
  }

  const formData = new FormData();
  formData.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/contracts/upload`, {
      method: "POST",
      body: formData,
    });
  } catch {
    return {
      status: "error",
      filename: file.name,
      contract_id: null,
      parsed_clauses: [],
      detail: NETWORK_ERROR_MESSAGE,
    };
  }

  const json = (await res.json().catch(() => null)) as UploadResponse | null;
  if (json && typeof json === "object" && "status" in json) return json;

  return {
    status: "error",
    filename: file.name,
    contract_id: null,
    parsed_clauses: [],
    detail: "Invalid response from backend.",
  };
}

// ---------------------------------------------------------------------------
// Contracts
// ---------------------------------------------------------------------------

export async function getContracts(): Promise<ContractSummary[]> {
  const data = await request<ContractListResponse>("/api/contracts");
  return data.contracts;
}

export async function getContract(id: string): Promise<ContractDetail> {
  return request<ContractDetail>(`/api/contracts/${encodeURIComponent(id)}`);
}

/**
 * Schedule an analysis run. Returns immediately (202) with the run to poll.
 * Pass `force` to re-analyze clauses the content-hash cache would skip.
 */
export async function analyzeContract(
  id: string,
  options?: { force?: boolean },
): Promise<AnalysisRun> {
  const params = options?.force ? "?force=true" : "";
  const data = await request<AnalyzeAcceptedResponse>(
    `/api/contracts/${encodeURIComponent(id)}/analyze${params}`,
    { method: "POST" },
  );
  return data.run;
}

export async function getAnalysisRun(runId: string): Promise<AnalysisRun> {
  const data = await request<AnalysisRunResponse>(
    `/api/analysis-runs/${encodeURIComponent(runId)}`,
  );
  return data.run;
}

export async function deleteContract(id: string): Promise<DeleteResponse> {
  return request<DeleteResponse>(`/api/contracts/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export async function getMetrics(): Promise<MetricsResponse> {
  return request<MetricsResponse>("/api/metrics");
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function register(email: string, password: string): Promise<UserInfo> {
  return request<UserInfo>("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email: string, password: string): Promise<UserInfo> {
  return request<UserInfo>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function logout(): Promise<void> {
  await request<unknown>("/api/auth/logout", { method: "POST" }).catch(() => undefined);
}

/** Resolves to the signed-in user, or null when there is no live session. */
export async function getSession(): Promise<UserInfo | null> {
  try {
    return await request<UserInfo>("/api/auth/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  const megabytes = bytes / (1024 * 1024);
  // "10 MB" reads better than "10.0 MB" for the round limit value.
  return `${Number.isInteger(megabytes) ? megabytes : megabytes.toFixed(1)} MB`;
}
