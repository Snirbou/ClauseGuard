import type { RiskDistribution } from "@/types/contracts";
import { pluralize } from "@/lib/format";

type Props = {
  distribution: RiskDistribution;
  clauseCount: number;
};

const BUCKETS = [
  { key: "high", label: "High", emoji: "🔴", bar: "bg-red-500", text: "text-red-700 dark:text-red-300" },
  { key: "medium", label: "Medium", emoji: "🟡", bar: "bg-amber-500", text: "text-amber-700 dark:text-amber-300" },
  { key: "low", label: "Low", emoji: "🟢", bar: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-300" },
  { key: "unanalyzed", label: "Not analyzed", emoji: "⚪", bar: "bg-zinc-400 dark:bg-zinc-600", text: "text-zinc-600 dark:text-zinc-400" },
] as const;

export default function RiskSummary({ distribution, clauseCount }: Props) {
  const total = clauseCount || 1; // avoid dividing by zero on an empty contract

  return (
    <section
      aria-label="Risk distribution"
      className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Risk overview
        </h2>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          {clauseCount} {pluralize(clauseCount, "clause")} total
        </p>
      </div>

      <div className="mt-4 flex h-2.5 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-900">
        {BUCKETS.map((bucket) => {
          const count = distribution[bucket.key];
          if (count === 0) return null;
          return (
            <div
              key={bucket.key}
              className={bucket.bar}
              style={{ width: `${(count / total) * 100}%` }}
              title={`${bucket.label}: ${count}`}
            />
          );
        })}
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {BUCKETS.map((bucket) => (
          <div key={bucket.key}>
            <dt className={`flex items-center gap-1.5 text-xs font-medium ${bucket.text}`}>
              <span aria-hidden="true">{bucket.emoji}</span>
              {bucket.label}
            </dt>
            <dd className="mt-0.5 text-2xl font-semibold tabular-nums">
              {distribution[bucket.key]}
            </dd>
          </div>
        ))}
      </dl>

      {distribution.high > 0 ? (
        <p className="mt-4 rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs leading-relaxed text-red-800 dark:text-red-200">
          {distribution.high} {pluralize(distribution.high, "clause")} flagged as
          high risk. Read {distribution.high === 1 ? "it" : "them"} carefully and
          consider having an attorney review the contract before signing.
        </p>
      ) : null}
    </section>
  );
}
