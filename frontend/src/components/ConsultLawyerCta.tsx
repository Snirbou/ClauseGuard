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
  const subject = encodeURIComponent(`Question about clause ${clauseIndex} in my contract`);
  const body = encodeURIComponent(
    `I would like advice on the following contract clause:\n\n"${clauseText}"\n\n` +
      "(Flagged as high risk by ClauseGuard, an automated tool. This is not legal advice.)",
  );

  return (
    <div className="mt-4 flex flex-col gap-2 rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-xs leading-relaxed text-red-800 dark:text-red-200">
        This clause was flagged as high risk. Have a qualified attorney review it
        before you sign.
      </p>
      <a
        href={`mailto:?subject=${subject}&body=${body}`}
        className="inline-flex shrink-0 items-center justify-center rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-red-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500"
      >
        Consult a Lawyer
      </a>
    </div>
  );
}
