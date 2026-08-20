import type { ContractFinding } from "@/types/contracts";
import { pluralize } from "@/lib/format";

const SEVERITY_STYLES: Record<string, { card: string; badge: string }> = {
  high: {
    card: "border-red-500/40 bg-red-500/5",
    badge: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
  },
  medium: {
    card: "border-amber-500/40 bg-amber-500/5",
    badge: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  },
};

/**
 * Contract-level missing-protection findings. What a contract does NOT say
 * is often the freelancer's biggest risk — these cards surface exactly that.
 */
export default function FindingsSection({ findings }: { findings: ContractFinding[] }) {
  if (findings.length === 0) return null;

  return (
    <section aria-label="Missing protections" className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-lg font-semibold tracking-tight">
          Missing protections
        </h2>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          {findings.length} {pluralize(findings.length, "gap")} detected
        </p>
      </div>

      <ul className="flex flex-col gap-3">
        {findings.map((finding) => {
          const styles = SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.medium;
          return (
            <li
              key={finding.id}
              className={`rounded-xl border p-4 ${styles.card}`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${styles.badge}`}
                >
                  {finding.severity}
                </span>
                <h3 className="text-sm font-semibold">{finding.title}</h3>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
                {finding.detail}
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
