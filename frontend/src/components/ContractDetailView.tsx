"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import type {
  AnalysisRun,
  ClauseDetail,
  ContractDetail,
  RiskLevel,
} from "@/types/contracts";
import { ApiError, analyzeContract, deleteContract, getContract } from "@/lib/api";
import ClauseCard from "@/components/ClauseCard";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import ErrorMessage from "@/components/ErrorMessage";
import FindingsSection from "@/components/FindingsSection";
import LoadingSpinner from "@/components/LoadingSpinner";
import RiskSummary from "@/components/RiskSummary";
import { apiErrorMessage } from "@/i18n";
import { useI18n } from "@/i18n/I18nProvider";
import { useRedirectOnAuthError } from "@/lib/useSession";
import { formatDateTime } from "@/lib/format";

type Filter = "all" | RiskLevel;

const FILTERS: readonly Filter[] = ["all", "high", "medium", "low"];

const POLL_INTERVAL_MS = 1200;

function isActiveRun(run: AnalysisRun | null | undefined): boolean {
  return run?.status === "pending" || run?.status === "running";
}

function AnalysisProgress({ run }: { run: AnalysisRun }) {
  const { dict } = useI18n();
  const total = run.clause_count ?? 0;
  const done = run.completed_clauses;
  const percent = total > 0 ? Math.round((done / total) * 100) : 5;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="flex items-center gap-2 font-semibold">
          <LoadingSpinner size="sm" />
          {dict.detail.progressTitle}
        </span>
        <span className="font-mono text-xs text-zinc-500 dark:text-zinc-400">
          {done}/{total}
        </span>
      </div>
      <div
        className="mt-3 h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-900"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={done}
        aria-label={dict.detail.progressAria}
      >
        <div
          className="h-full rounded-full bg-zinc-900 transition-all duration-500 dark:bg-zinc-100"
          style={{ width: `${Math.max(percent, 5)}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
        {dict.detail.progressHint}
      </p>
    </div>
  );
}

export default function ContractDetailView({ contractId }: { contractId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { dict, intl } = useI18n();

  const [filter, setFilter] = useState<Filter>("all");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const detailQuery = useQuery<ContractDetail, unknown>({
    queryKey: ["contract", contractId],
    queryFn: () => getContract(contractId),
    // While a run is active the detail response changes every second or two:
    // latest_run.completed_clauses advances and finished clauses gain risk
    // fields. One polled query drives the whole page.
    refetchInterval: (query) =>
      isActiveRun(query.state.data?.latest_run) ? POLL_INTERVAL_MS : false,
    // Keep polling even when the tab is hidden — otherwise a user who tabs
    // away mid-run comes back to a page frozen on a stale progress bar.
    refetchIntervalInBackground: true,
  });

  // A 401 mid-session redirects to /login instead of a looping Retry.
  useRedirectOnAuthError(detailQuery.error);

  const contract = detailQuery.data;
  const activeRun = isActiveRun(contract?.latest_run) ? contract?.latest_run : null;
  const failedRun =
    contract?.latest_run?.status === "failed" ? contract.latest_run : null;

  const analyzeMutation = useMutation({
    mutationFn: (options?: { force?: boolean }) => analyzeContract(contractId, options),
    onSettled: () => {
      // Success or 409, the server state changed (or we learned it) — refetch.
      void queryClient.invalidateQueries({ queryKey: ["contract", contractId] });
    },
  });

  const onDelete = useCallback(async () => {
    if (!contract) return;
    const confirmed = window.confirm(
      dict.contracts.confirmDelete(contract.original_filename, contract.clause_count),
    );
    if (!confirmed) return;

    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteContract(contractId);
      void queryClient.invalidateQueries({ queryKey: ["contracts"] });
      router.push("/contracts");
    } catch (err) {
      // Previously swallowed — the user confirmed a delete and saw nothing.
      setDeleteError(apiErrorMessage(dict, err, dict.contracts.deleteFailed));
      setDeleting(false);
    }
  }, [contract, contractId, dict, queryClient, router]);

  const visibleClauses = useMemo(
    () =>
      contract?.clauses.filter(
        (clause: ClauseDetail) => filter === "all" || clause.risk_level === filter,
      ) ?? [],
    [contract, filter],
  );

  if (detailQuery.isPending) {
    return <LoadingSpinner block label={dict.detail.loading} />;
  }

  if (detailQuery.isError || !contract) {
    return (
      <div className="flex flex-col gap-4">
        <ErrorMessage
          title={dict.detail.loadFailedTitle}
          message={apiErrorMessage(dict, detailQuery.error, dict.detail.loadFailed)}
          onRetry={() => void detailQuery.refetch()}
        />
        <Link
          href="/contracts"
          className="text-sm font-semibold text-zinc-600 underline underline-offset-2 dark:text-zinc-400"
        >
          {dict.detail.backToAll}
        </Link>
      </div>
    );
  }

  const analyzing = analyzeMutation.isPending || Boolean(activeRun);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          href="/contracts"
          className="text-sm font-medium text-zinc-600 transition-colors hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          {dict.detail.allContracts}
        </Link>
      </div>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1
            className="break-words text-2xl font-semibold tracking-tight sm:text-3xl"
            dir="ltr"
          >
            {contract.original_filename}
          </h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            {dict.detail.uploaded(formatDateTime(contract.created_at, intl))} ·{" "}
            {dict.common.clauses(contract.clause_count)} ·{" "}
            {contract.has_analysis
              ? dict.detail.analyzedCount(contract.analyzed_clause_count)
              : dict.detail.notAnalyzedYet}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => analyzeMutation.mutate(undefined)}
            disabled={analyzing || deleting || contract.clause_count === 0}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            {analyzing ? (
              <>
                <LoadingSpinner size="sm" />
                {dict.detail.analyzing}
              </>
            ) : contract.has_analysis ? (
              dict.detail.rerun
            ) : (
              dict.detail.analyze
            )}
          </button>

          <button
            type="button"
            onClick={() => void onDelete()}
            disabled={analyzing || deleting}
            className="inline-flex items-center justify-center rounded-lg border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-600 transition-colors hover:border-red-400 hover:bg-red-500/10 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-400 dark:hover:text-red-400"
          >
            {deleting ? dict.common.deleting : dict.common.delete}
          </button>
        </div>
      </header>

      {/* A 409 means a run is already active — the progress bar below already
          conveys that, so don't also show a failure banner. */}
      {analyzeMutation.isError &&
      !(analyzeMutation.error instanceof ApiError && analyzeMutation.error.status === 409) ? (
        <ErrorMessage
          title={dict.detail.startFailedTitle}
          message={apiErrorMessage(dict, analyzeMutation.error, dict.detail.startFailed)}
        />
      ) : null}

      {deleteError ? (
        <ErrorMessage title={dict.detail.deleteFailedTitle} message={deleteError} />
      ) : null}

      {failedRun?.error_message && !analyzing ? (
        <ErrorMessage title={dict.detail.lastRunFailedTitle} message={failedRun.error_message} />
      ) : null}

      {activeRun ? <AnalysisProgress run={activeRun} /> : null}

      <RiskSummary
        distribution={contract.risk_distribution}
        clauseCount={contract.clause_count}
      />

      {contract.analysis_summary ? (
        <section
          aria-label={dict.detail.executiveSummary}
          className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            {dict.detail.executiveSummary}
          </h2>
          {/* LLM output stays in the language of the contract (English). */}
          <p
            className="mt-2 text-start text-sm leading-relaxed text-zinc-800 dark:text-zinc-100"
            dir="ltr"
            lang="en"
          >
            {contract.analysis_summary}
          </p>
        </section>
      ) : null}

      <FindingsSection findings={contract.findings ?? []} />

      <DisclaimerBanner variant="full" />

      {!contract.has_analysis && !analyzing ? (
        <div className="rounded-xl border border-dashed border-zinc-300 px-4 py-8 text-center dark:border-zinc-800">
          <p className="text-2xl" aria-hidden="true">
            🤖
          </p>
          <h2 className="mt-2 font-semibold">{dict.detail.noAnalysisTitle}</h2>
          <p className="mx-auto mt-1 max-w-md text-sm text-zinc-600 dark:text-zinc-400">
            {dict.detail.noAnalysisBody}
          </p>
        </div>
      ) : null}

      <section className="flex flex-col gap-4">
        {/* Non-English locales only: the clauses below stay in English. */}
        {dict.detail.englishNote ? (
          <p className="text-xs text-zinc-500 dark:text-zinc-400">{dict.detail.englishNote}</p>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight">{dict.detail.clausesTitle}</h2>

          {contract.has_analysis ? (
            <div
              className="flex flex-wrap items-center gap-1"
              role="group"
              aria-label={dict.detail.filterAria}
            >
              {FILTERS.map((key) => {
                const active = filter === key;
                return (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setFilter(key)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                      active
                        ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                        : "border border-zinc-300 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
                    }`}
                  >
                    {dict.detail.filters[key]}
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>

        {visibleClauses.length === 0 ? (
          <p className="rounded-xl border border-dashed border-zinc-300 px-4 py-8 text-center text-sm text-zinc-600 dark:border-zinc-800 dark:text-zinc-400">
            {dict.detail.noMatch}
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
