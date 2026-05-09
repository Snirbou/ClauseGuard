import "server-only";

import { cookies } from "next/headers";

import { AUTH_TOKEN_COOKIE } from "@/lib/auth-constants";
import { getAuthMode } from "@/lib/auth-service";
import type { UserContractSummary } from "@/types/contracts";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function authHeaders(): Promise<HeadersInit> {
  const jar = await cookies();
  const token = jar.get(AUTH_TOKEN_COOKIE)?.value;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchUserContractsServer(): Promise<UserContractSummary[]> {
  if (getAuthMode() === "mock") {
    await new Promise((r) => setTimeout(r, 600));
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

  const res = await fetch(`${API_BASE_URL}/api/contracts`, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  if (!res.ok) return [];
  const json = (await res.json().catch(() => null)) as UserContractSummary[] | null;
  return Array.isArray(json) ? json : [];
}
