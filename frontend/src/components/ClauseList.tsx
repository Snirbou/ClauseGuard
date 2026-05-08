"use client";

import type { ParsedClause } from "@/types/contracts";

type Props = {
  filename: string;
  clauses: ParsedClause[];
};

export default function ClauseList({ filename, clauses }: Props) {
  return (
    <div className="mt-6 w-full">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-zinc-700 dark:text-zinc-200">
            Parsed clauses
          </div>
          <div className="text-xs text-zinc-500 dark:text-zinc-400">
            {filename}
          </div>
        </div>
        <div className="text-xs font-semibold text-zinc-600 dark:text-zinc-300">
          {clauses.length} clause{clauses.length === 1 ? "" : "s"}
        </div>
      </div>

      <div className="mt-3 max-h-[60vh] space-y-3 overflow-auto pr-2">
        {clauses.map((clause) => (
          <div
            key={clause.clause_index}
            className="rounded-lg border border-zinc-200 bg-white p-3 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
          >
            <div className="mb-2 flex items-center gap-2">
              <span className="text-xs font-mono font-semibold text-zinc-600 dark:text-zinc-300">
                Clause {clause.clause_index}
              </span>
              <span className="rounded-md border border-zinc-300 bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200">
                {clause.clause_type}
              </span>
              <span className="text-[11px] tabular-nums text-zinc-500 dark:text-zinc-400">
                {(clause.clause_type_confidence * 100).toFixed(0)}%
              </span>
            </div>
            <pre className="whitespace-pre-wrap break-words text-sm leading-relaxed text-zinc-800 dark:text-zinc-100">
              {clause.raw_text}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}

