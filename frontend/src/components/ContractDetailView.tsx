"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ClauseDetail, ContractDetail, RiskLevel } from "@/types/contracts";
import { ApiError, analyzeContract, deleteContract, getContract } from "@/lib/api";
import ClauseCard from "@/components/ClauseCard";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import ErrorMessage from "@/components/ErrorMessage";
import LoadingSpinner from "@/components/LoadingSpinner";
import RiskSummary from "@/components/RiskSummary";
import { formatDateTime, pluralize } from "@/lib/format";

type Filter = "all" | RiskLevel;

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "high", label: "🔴 High" },
  { key: "medium", label: "🟡 Medium" },
  { key: "low", label: "🟢 Low" },
];

function matchesFilter(clause: ClauseDetail, filter: Filter): boolean {
  return filter === "all" || clause.risk_level === filter;
}

export default function ContractDetailView({ contractId }: { contractId: string }) {
  const router = useRouter();

  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");

  const load = useCallback(async () => {
    setLoadError(null);
    setContract(null);
    try {
      setContract(await getContract(contractId));
    } catch (err) {
      setLoadError(
        err instanceof ApiError ? err.message : "Could not load this contract.",
      );
    }
  }, [contractId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onAnalyze = useCallback(async () => {
    setAnalyzing(true);
    setActionError(null);
    try {
      await analyzeContract(contractId);
      // Re-fetch rather than merging the analyze response, so the view always
      // reflects exactly what was persisted.
      setContract(await getContract(contractId));
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Analysis failed. Please try again.",
      );
    } finally {
      setAnalyzing(false);
    }
  }, [contractId]);

  const onDelete = useCallback(async () => {
    if (!contract) return;
    const confirmed = window.confirm(
      `Delete "${contract.original_filename}"?\n\nThis permanently removes the contract, its ${contract.clause_count} ${pluralize(
        contract.clause_count,
        "clause",
      )} and any analysis. This cannot be undone.`,
    );
    if (!confirmed) return;

    setDeleting(true);
    setActionError(null);
    try {
      await deleteContract(contractId);
      router.push("/contracts");
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Could not delete the contract.",
      );
      setDeleting(false);
    }
  }, [contract, contractId, router]);

  const visibleClauses = useMemo(
    () => contract?.clauses.filter((clause) => matchesFilter(clause, filter)) ?? [],
    [contract, filter],
  );

  if (contract === null && !loadError) {
    return <LoadingSpinner block label="Loading contract…" />;
  }

  if (loadError) {
    return (
      <div className="flex flex-col gap-4">
        <ErrorMessage
          title="Could not load this contract"
          message={loadError}
          onRetry={() => void load()}
        />
        <Link
          href="/contracts"
          className="text-sm font-semibold text-zinc-600 underline underline-offset-2 dark:text-zinc-400"
        >
          ← Back to all contracts
        </Link>
      </div>
    );
  }

  if (!contract) return null;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          href="/contracts"
          className="text-sm font-medium text-zinc-600 transition-colors hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          ← All contracts
        </Link>
      </div>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight break-words sm:text-3xl">
            {contract.original_filename}
          </h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Uploaded {formatDateTime(contract.created_at)} ·{" "}
            {contract.clause_count} {pluralize(contract.clause_count, "clause")} ·{" "}
            {contract.has_analysis
              ? `${contract.analyzed_clause_count} analyzed`
              : "not analyzed yet"}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void onAnalyze()}
            disabled={analyzing || deleting || contract.clause_count === 0}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            {analyzing ? (
              <>
                <LoadingSpinner size="sm" />
                Analyzing…
              </>
            ) : contract.has_analysis ? (
              "Re-run analysis"
            ) : (
              "Analyze contract"
            )}
          </button>

          <button
            type="button"
            onClick={() => void onDelete()}
            disabled={analyzing || deleting}
            className="inline-flex items-center justify-center rounded-lg border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-600 transition-colors hover:border-red-400 hover:bg-red-500/10 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-400 dark:hover:text-red-400"
          >
            {deleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </header>

      {actionError ? (
        <ErrorMessage title="Something went wrong" message={actionError} />
      ) : null}

      {analyzing ? (
        <div className="rounded-xl border border-zinc-200 bg-white px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950">
          <LoadingSpinner
            label={`Analyzing ${contract.clause_count} ${pluralize(
              contract.clause_count,
              "clause",
            )} with the AI model. This runs one request per clause and can take a minute — keep this tab open.`}
          />
        </div>
      ) : null}

      <RiskSummary
        distribution={contract.risk_distribution}
        clauseCount={contract.clause_count}
      />

      <DisclaimerBanner variant="full" />

      {!contract.has_analysis && !analyzing ? (
        <div className="rounded-xl border border-dashed border-zinc-300 px-4 py-8 text-center dark:border-zinc-800">
          <p className="text-2xl" aria-hidden="true">
            🤖
          </p>
          <h2 className="mt-2 font-semibold">No analysis yet</h2>
          <p className="mx-auto mt-1 max-w-md text-sm text-zinc-600 dark:text-zinc-400">
            Clauses have been extracted and classified. Run the analysis to get
            a plain-language summary and risk assessment for each one.
          </p>
        </div>
      ) : null}

      <section className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight">Clauses</h2>

          {contract.has_analysis ? (
            <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Filter by risk level">
              {FILTERS.map((option) => {
                const active = filter === option.key;
                return (
                  <button
                    key={option.key}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setFilter(option.key)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                      active
                        ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                        : "border border-zinc-300 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
                    }`}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>

        {visibleClauses.length === 0 ? (
          <p className="rounded-xl border border-dashed border-zinc-300 px-4 py-8 text-center text-sm text-zinc-600 dark:border-zinc-800 dark:text-zinc-400">
            No clauses match this filter.
          </p>
        ) : (
          <ul className="flex flex-col gap-4">
            {visibleClauses.map((clause) => (
              <ClauseCard key={clause.parsed_clause_id} clause={clause} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
