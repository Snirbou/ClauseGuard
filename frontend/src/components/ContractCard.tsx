"use client";

import Link from "next/link";
import type { ContractSummary } from "@/types/contracts";
import { formatDateTime, pluralize } from "@/lib/format";

type Props = {
  contract: ContractSummary;
  onDelete?: (contract: ContractSummary) => void;
  deleting?: boolean;
};

function AnalysisStatus({ contract }: { contract: ContractSummary }) {
  if (!contract.has_analysis) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300 bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-400">
        Not analyzed
      </span>
    );
  }

  const partial = contract.analyzed_clause_count < contract.clause_count;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${
        partial
          ? "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300"
          : "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
      }`}
    >
      {partial
        ? `Partly analyzed ${contract.analyzed_clause_count}/${contract.clause_count}`
        : "Analyzed"}
    </span>
  );
}

export default function ContractCard({ contract, onDelete, deleting = false }: Props) {
  return (
    <li className="group relative rounded-xl border border-zinc-200 bg-white p-4 shadow-sm transition-colors hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-700">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <Link
            href={`/contracts/${contract.id}`}
            className="block truncate text-base font-semibold text-zinc-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:text-zinc-50"
          >
            {/* Stretches over the whole card so the entire surface is clickable,
                while the delete button below stays above it via z-index. */}
            <span className="absolute inset-0 rounded-xl" aria-hidden="true" />
            {contract.original_filename}
          </Link>

          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            {formatDateTime(contract.created_at)} ·{" "}
            {contract.clause_count} {pluralize(contract.clause_count, "clause")}
          </p>
        </div>

        <div className="relative z-[1] flex shrink-0 items-center gap-2">
          <AnalysisStatus contract={contract} />
          {onDelete ? (
            <button
              type="button"
              disabled={deleting}
              onClick={() => onDelete(contract)}
              aria-label={`Delete ${contract.original_filename}`}
              className="rounded-lg border border-zinc-200 px-2.5 py-1 text-xs font-semibold text-zinc-500 transition-colors hover:border-red-400 hover:bg-red-500/10 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-800 dark:text-zinc-400 dark:hover:text-red-400"
            >
              {deleting ? "Deleting…" : "Delete"}
            </button>
          ) : null}
        </div>
      </div>
    </li>
  );
}
