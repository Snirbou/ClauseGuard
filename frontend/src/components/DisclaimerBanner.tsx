/**
 * Unauthorized-Practice-of-Law disclaimer.
 *
 * Deliberately has no dismiss control: the PRD requires it to be visible on
 * every screen that presents analysis output, so it renders in the root
 * layout and cannot be closed.
 */

import DisclaimerLogger from "@/components/DisclaimerLogger";

type Props = {
  /** `compact` is the always-on layout strip; `full` is the in-page callout. */
  variant?: "compact" | "full";
};

export const DISCLAIMER_TEXT =
  "This tool provides educational, pattern-based analysis only. It is NOT legal advice. Always consult a qualified attorney.";

export default function DisclaimerBanner({ variant = "compact" }: Props) {
  if (variant === "full") {
    return (
      <aside
        role="note"
        className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200"
      >
        <p className="font-semibold">Not legal advice</p>
        <p className="mt-1 leading-relaxed">{DISCLAIMER_TEXT}</p>
      </aside>
    );
  }

  return (
    <div
      role="note"
      className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-center text-xs leading-relaxed text-amber-900 dark:text-amber-200"
    >
      <span aria-hidden="true">⚠️ </span>
      {DISCLAIMER_TEXT}
      {/* AC-X05: every render of this banner is logged server-side. */}
      <DisclaimerLogger />
    </div>
  );
}
