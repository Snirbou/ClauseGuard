"use client";

import type { RiskLevel } from "@/types/contracts";
import { useI18n } from "@/i18n/I18nProvider";
import { RISK_EMOJI, formatRiskScore, riskLevelLabel } from "@/lib/format";

const LEVEL_STYLES: Record<RiskLevel, string> = {
  high: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
  medium: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  low: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
};

const UNANALYZED_STYLE =
  "border-zinc-300 bg-zinc-100 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-400";

type Props = {
  level: RiskLevel | null;
  /** When provided, the numeric score is shown alongside the level. */
  score?: number | null;
  size?: "sm" | "md";
};

export default function RiskBadge({ level, score, size = "md" }: Props) {
  const { dict } = useI18n();
  const style = level ? LEVEL_STYLES[level] : UNANALYZED_STYLE;
  const sizing = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";
  const scoreText = formatRiskScore(score ?? null);

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${sizing} ${style}`}
    >
      {level ? <span aria-hidden="true">{RISK_EMOJI[level]}</span> : null}
      <span className="uppercase">{riskLevelLabel(dict, level)}</span>
      {scoreText ? (
        <span className="font-mono font-normal opacity-70">{scoreText}</span>
      ) : null}
    </span>
  );
}
