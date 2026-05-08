"use client";

import { useEffect, useRef, useState } from "react";
import type { ContractResultsResponse } from "@/types/contracts";
import { fetchContractResults } from "@/lib/api";
import ClauseCard from "@/components/ClauseCard";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import ConsultLawyerCTA from "@/components/ConsultLawyerCTA";

type Props = {
  contractId: string;
  filename?: string;
};

const POLL_INTERVAL_MS = 3000;
const POLL_MAX_ATTEMPTS = 20; // ~60s ceiling

const FALLBACK_DISCLAIMER =
  "ClauseGuard provides informational analysis only. It is not legal advice. " +
  "Consult a qualified lawyer for advice on your specific contract.";

function anyPending(resp: ContractResultsResponse): boolean {
  if (resp.status !== "success") return false;
  return resp.clauses.some((c) => c.risk_level === null);
}

export default function ResultsView({ contractId, filename }: Props) {
  const [data, setData] = useState<ContractResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const attemptsRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      try {
        const resp = await fetchContractResults(contractId);
        if (cancelled) return;
        setData(resp);
        setLoading(false);
        if (resp.status === "error") {
          setError(resp.detail);
          return;
        }
        attemptsRef.current += 1;
        if (anyPending(resp) && attemptsRef.current < POLL_MAX_ATTEMPTS) {
          timer = setTimeout(tick, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Unknown error");
        setLoading(false);
      }
    }

    void tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [contractId]);

  const disclaimer =
    (data && data.status === "success" && data.disclaimer) ||
    (data && data.status === "error" && data.disclaimer) ||
    FALLBACK_DISCLAIMER;

  const displayFilename = filename ?? data?.filename ?? null;

  return (
    <section className="mt-6 w-full">
      <DisclaimerBanner text={disclaimer} />

      <div className="flex items-baseline justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-zinc-700 dark:text-zinc-200">
            Analysis
          </div>
          {displayFilename && (
            <div className="text-xs text-zinc-500 dark:text-zinc-400">
              {displayFilename}
            </div>
          )}
        </div>
        {data && data.status === "success" && (
          <div className="text-xs font-semibold text-zinc-600 dark:text-zinc-300">
            {data.clauses.length} clause{data.clauses.length === 1 ? "" : "s"}
            {anyPending(data) && (
              <span className="ml-2 font-normal text-zinc-500 dark:text-zinc-400">
                (analysis in progress…)
              </span>
            )}
          </div>
        )}
      </div>

      {loading && !data && (
        <div className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
          Loading analysis…
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {data && data.status === "success" && (
        <div className="mt-3 space-y-3">
          {data.clauses.map((clause) => (
            <ClauseCard key={clause.parsed_clause_id} clause={clause} />
          ))}
        </div>
      )}

      <ConsultLawyerCTA />
    </section>
  );
}
