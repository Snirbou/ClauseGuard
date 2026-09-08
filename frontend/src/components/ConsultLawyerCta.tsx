"use client";

import { useI18n } from "@/i18n/I18nProvider";

/**
 * Shown next to high-risk clauses. Intentionally does not link anywhere:
 * recommending a specific firm would edge toward the legal-referral territory
 * the UPL guidance in the PRD tells us to stay out of. It nudges the user to
 * seek human counsel and hands them the clause text to bring along.
 */

type Props = {
  clauseIndex: number;
  clauseText: string;
};

export default function ConsultLawyerCta({ clauseIndex, clauseText }: Props) {
  const { dict } = useI18n();
  const subject = encodeURIComponent(dict.cta.mailSubject(clauseIndex));
  const body = encodeURIComponent(dict.cta.mailBody(clauseText));

  return (
    <div className="mt-4 flex flex-col gap-2 rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-xs leading-relaxed text-red-800 dark:text-red-200">
        {dict.cta.flagged}
      </p>
      <a
        href={`mailto:?subject=${subject}&body=${body}`}
        className="inline-flex shrink-0 items-center justify-center rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-red-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500"
      >
        {dict.cta.consult}
      </a>
    </div>
  );
}
