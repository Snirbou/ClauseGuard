"use client";

import { useState } from "react";
import type { ClauseDetail } from "@/types/contracts";
import ClauseTypeTag from "@/components/ClauseTypeTag";
import ConsultLawyerCta from "@/components/ConsultLawyerCta";
import RiskBadge from "@/components/RiskBadge";

/** Clause text longer than this is collapsed behind a "Show full text" toggle. */
const COLLAPSE_THRESHOLD = 400;

type Props = {
  clause: ClauseDetail;
};

export default function ClauseCard({ clause }: Props) {
  const isLong = clause.raw_text.length > COLLAPSE_THRESHOLD;
  const [expanded, setExpanded] = useState(false);

  const visibleText =
    isLong && !expanded
      ? `${clause.raw_text.slice(0, COLLAPSE_THRESHOLD).trimEnd()}…`
      : clause.raw_text;

  const analyzed = clause.risk_level !== null;

  return (
    <li className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs font-semibold text-zinc-500 dark:text-zinc-400">
          #{clause.clause_index}
        </span>
        <ClauseTypeTag
          clauseType={clause.clause_type}
          confidence={clause.clause_type_confidence}
        />
        <span className="ml-auto">
          <RiskBadge level={clause.risk_level} score={clause.risk_score} />
        </span>
      </div>

      <div className="mt-3">
        <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-zinc-800 dark:text-zinc-100">
          {visibleText}
        </p>
        {isLong ? (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            className="mt-2 text-xs font-semibold text-zinc-600 underline underline-offset-2 transition-colors hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
          >
            {expanded ? "Show less" : "Show full text"}
          </button>
        ) : null}
      </div>

      {analyzed ? (
        <div className="mt-4 flex flex-col gap-4 border-t border-zinc-200 pt-4 dark:border-zinc-800">
          {clause.plain_language_summary ? (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                What this means
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-zinc-800 dark:text-zinc-100">
                {clause.plain_language_summary}
              </p>
            </div>
          ) : null}

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Risk factors
            </h3>
            {clause.risk_factors.length > 0 ? (
              <ul className="mt-1.5 flex flex-col gap-1.5">
                {clause.risk_factors.map((factor, index) => (
                  <li
                    key={`${clause.parsed_clause_id}-factor-${index}`}
                    className="flex gap-2 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300"
                  >
                    <span aria-hidden="true" className="text-zinc-400">
                      •
                    </span>
                    <span>{factor}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1.5 text-sm text-zinc-500 dark:text-zinc-400">
                No specific risk factors identified.
              </p>
            )}
          </div>

          {clause.risk_level === "high" ? (
            <ConsultLawyerCta
              clauseIndex={clause.clause_index}
              clauseText={clause.raw_text}
            />
          ) : null}
        </div>
      ) : (
        <p className="mt-4 border-t border-zinc-200 pt-4 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
          This clause has not been analyzed yet.
        </p>
      )}
    </li>
  );
}
