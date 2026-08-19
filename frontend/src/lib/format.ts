import type { RiskLevel } from "@/types/contracts";

/**
 * Human labels for the clause types produced by `backend/classifier.py`.
 * Anything not listed falls back to a title-cased version of the raw value,
 * so a new classifier category still renders sensibly.
 */
const CLAUSE_TYPE_LABELS: Record<string, string> = {
  ip_assignment: "IP Assignment",
  payment_terms: "Payment Terms",
  termination: "Termination",
  liability: "Liability",
  confidentiality: "Confidentiality",
  scope_of_work: "Scope of Work",
  governing_law: "Governing Law",
  general: "General",
};

export function clauseTypeLabel(clauseType: string | null): string {
  if (!clauseType) return "Unclassified";
  const known = CLAUSE_TYPE_LABELS[clauseType];
  if (known) return known;
  return clauseType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function riskLevelLabel(level: RiskLevel | null): string {
  if (!level) return "Not analyzed";
  return level.toUpperCase();
}

export const RISK_EMOJI: Record<RiskLevel, string> = {
  high: "🔴",
  medium: "🟡",
  low: "🟢",
};

/**
 * Dates arrive as ISO strings from the API. Rendering them with the visitor's
 * locale on the server and again on the client causes a hydration mismatch, so
 * every caller of this must be inside a client component.
 */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleString(undefined, {
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

export function pluralize(count: number, singular: string, plural?: string): string {
  return count === 1 ? singular : (plural ?? `${singular}s`);
}
