"use client";

import type { ParsedClause } from "@/types/contracts";
import ClauseTypeTag from "@/components/ClauseTypeTag";
import { useI18n } from "@/i18n/I18nProvider";

type Props = {
  filename: string;
  clauses: ParsedClause[];
};

/**
 * The immediate post-upload view: clause text plus its classifier tag.
 * Risk analysis has not run at this point — that lives on the detail page.
 */
export default function ClauseList({ filename, clauses }: Props) {
  const { dict } = useI18n();

  return (
    <div className="w-full">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-200">
            {dict.upload.parsedClauses}
          </h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            <span dir="ltr">{filename}</span>
          </p>
        </div>
        <p className="text-xs font-semibold text-zinc-600 dark:text-zinc-300">
          {dict.common.clauses(clauses.length)}
        </p>
      </div>

      <ul className="mt-3 max-h-[60vh] space-y-3 overflow-auto pe-2">
        {clauses.map((clause) => (
          <li
            key={clause.parsed_clause_id ?? clause.clause_index}
            className="rounded-lg border border-zinc-200 bg-white p-3 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
          >
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs font-semibold text-zinc-500 dark:text-zinc-400">
                #{clause.clause_index}
              </span>
              <ClauseTypeTag
                clauseType={clause.clause_type}
                confidence={clause.clause_type_confidence}
              />
            </div>
            {/* Contract text is never translated: it stays in the contract's language. */}
            <p
              dir="ltr"
              lang="en"
              className="whitespace-pre-wrap break-words text-start text-sm leading-relaxed text-zinc-800 dark:text-zinc-100"
            >
              {clause.raw_text}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
