"use client";

import { useI18n } from "@/i18n/I18nProvider";
import { clauseTypeLabel, formatConfidence } from "@/lib/format";

/** One colour per classifier category, so a clause type is recognisable at a glance. */
const TYPE_STYLES: Record<string, string> = {
  ip_assignment: "border-violet-500/40 bg-violet-500/10 text-violet-700 dark:text-violet-300",
  payment_terms: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  termination: "border-orange-500/40 bg-orange-500/10 text-orange-700 dark:text-orange-300",
  liability: "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300",
  confidentiality: "border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-300",
  scope_of_work: "border-indigo-500/40 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300",
  governing_law: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
};

const DEFAULT_STYLE =
  "border-zinc-300 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-300";

type Props = {
  clauseType: string | null;
  confidence?: number | null;
};

export default function ClauseTypeTag({ clauseType, confidence }: Props) {
  const { dict } = useI18n();
  const style = (clauseType && TYPE_STYLES[clauseType]) || DEFAULT_STYLE;
  const confidenceText = formatConfidence(confidence ?? null);

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${style}`}
      title={confidenceText ? dict.clause.confidenceTitle(confidenceText) : undefined}
    >
      <span>{clauseTypeLabel(dict, clauseType)}</span>
      {confidenceText ? (
        <span className="font-mono font-normal opacity-70">{confidenceText}</span>
      ) : null}
    </span>
  );
}
