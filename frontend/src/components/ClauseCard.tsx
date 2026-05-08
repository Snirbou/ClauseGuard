"use client";

import { useState } from "react";
import type { ClauseResult, RiskLevel } from "@/types/contracts";

type Props = {
  clause: ClauseResult;
};

const RISK_BADGE: Record<RiskLevel, string> = {
  high: "border-red-300 bg-red-50 text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200",
  medium:
    "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200",
  low: "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200",
};

const RISK_LABEL: Record<RiskLevel, string> = {
  high: "Risk level: high (informational)",
  medium: "Risk level: medium (informational)",
  low: "Risk level: low (informational)",
};

function RiskBadge({ level }: { level: RiskLevel | null }) {
  if (!level) {
    return (
      <span className="rounded-md border border-zinc-300 bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
        Analysis pending
      </span>
    );
  }
  return (
    <span
      className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${RISK_BADGE[level]}`}
      aria-label={RISK_LABEL[level]}
      title={RISK_LABEL[level]}
    >
      {level}
    </span>
  );
}

export default function ClauseCard({ clause }: Props) {
  const [expanded, setExpanded] = useState(false);
  const hasL2 = clause.plain_language_summary !== null;
  const factors = clause.risk_factors ?? [];

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs font-semibold text-zinc-600 dark:text-zinc-300">
          Clause {clause.clause_index}
        </span>
        <span className="rounded-md border border-zinc-300 bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200">
          {clause.clause_type}
        </span>
        <RiskBadge level={clause.risk_level} />
      </div>

      <p className="text-sm leading-relaxed text-zinc-800 dark:text-zinc-100">
        {hasL2 ? clause.plain_language_summary : (
          <span className="italic text-zinc-500 dark:text-zinc-400">
            Analysis pending — DSPy summary not yet generated for this clause.
          </span>
        )}
      </p>

      {hasL2 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-3 inline-flex items-center gap-1 rounded-md border border-zinc-300 bg-zinc-50 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
        >
          {expanded ? "Hide detected patterns" : "Show detected patterns"}
        </button>
      )}

      {expanded && hasL2 && (
        <div className="mt-3 border-t border-zinc-200 pt-3 dark:border-zinc-800">
          <div className="text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-300">
            Detected patterns
          </div>
          {factors.length > 0 ? (
            <ul className="mt-1 list-disc pl-5 text-sm leading-relaxed text-zinc-800 dark:text-zinc-100">
              {factors.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-sm italic text-zinc-500 dark:text-zinc-400">
              No specific patterns flagged.
            </p>
          )}

          <details className="mt-3 text-xs text-zinc-600 dark:text-zinc-400">
            <summary className="cursor-pointer select-none font-semibold text-zinc-700 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-zinc-100">
              Original clause text
            </summary>
            <pre className="mt-2 whitespace-pre-wrap break-words rounded-md bg-zinc-50 p-2 font-mono text-[11px] leading-relaxed text-zinc-700 dark:bg-zinc-900 dark:text-zinc-200">
              {clause.raw_text}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}
