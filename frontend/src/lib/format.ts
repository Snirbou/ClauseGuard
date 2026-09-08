import type { Dictionary } from "@/i18n/en";
import type { RiskLevel } from "@/types/contracts";

/**
 * Human label for a classifier category. Anything the dictionary does not
 * list falls back to a title-cased version of the raw value, so a new
 * classifier category still renders sensibly.
 */
export function clauseTypeLabel(dict: Dictionary, clauseType: string | null): string {
  if (!clauseType) return dict.clause.unclassified;
  const known = dict.clauseTypes[clauseType];
  if (known) return known;
  return clauseType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function riskLevelLabel(dict: Dictionary, level: RiskLevel | null): string {
  if (!level) return dict.risk.unanalyzed;
  return dict.risk.levels[level];
}

export const RISK_EMOJI: Record<RiskLevel, string> = {
  high: "🔴",
  medium: "🟡",
  low: "🟢",
};

/**
 * Dates arrive as ISO strings from the API. Rendering them on the server and
 * again on the client with different clocks/time zones causes a hydration
 * mismatch, so every caller of this must be inside a client component.
 * `locale` is the BCP 47 tag from `useI18n().intl`.
 */
export function formatDateTime(iso: string, locale?: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatConfidence(confidence: number | null): string | null {
  if (confidence === null || Number.isNaN(confidence)) return null;
  return `${Math.round(confidence * 100)}%`;
}

export function formatRiskScore(score: number | null): string | null {
  if (score === null || Number.isNaN(score)) return null;
  return score.toFixed(2);
}
