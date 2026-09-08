"use client";

import type { ContractFinding } from "@/types/contracts";
import { useI18n } from "@/i18n/I18nProvider";

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
 *
 * Copy is looked up by `pain_point` in the dictionary; a pain point the
 * dictionary does not know falls back to the server's English title/detail,
 * rendered as explicit LTR English so it reads correctly in an RTL layout.
 */
export default function FindingsSection({ findings }: { findings: ContractFinding[] }) {
  const { dict } = useI18n();
  if (findings.length === 0) return null;

  return (
    <section aria-label={dict.findings.title} className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-lg font-semibold tracking-tight">{dict.findings.title}</h2>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          {dict.findings.gaps(findings.length)}
        </p>
      </div>

      <ul className="flex flex-col gap-3">
        {findings.map((finding) => {
          const styles = SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.medium;
          const t = dict.findings.byPainPoint[finding.pain_point];
          // Server text is English regardless of the UI locale (never
          // translate model/contract output), so mark it as such when used.
          const englishFallback = t === undefined;
          const englishProps = englishFallback ? { dir: "ltr", lang: "en" } : {};
          const englishClass = englishFallback ? " text-start" : "";
          return (
            <li
              key={finding.id}
              className={`rounded-xl border p-4 ${styles.card}`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${styles.badge}`}
                >
                  {dict.findings.severity[finding.severity] ?? finding.severity}
                </span>
                <h3 className={`text-sm font-semibold${englishClass}`} {...englishProps}>
                  {t?.title ?? finding.title}
                </h3>
              </div>
              <p
                className={`mt-2 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300${englishClass}`}
                {...englishProps}
              >
                {t?.detail ?? finding.detail}
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
