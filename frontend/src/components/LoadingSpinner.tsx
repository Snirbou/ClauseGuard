"use client";

import { useI18n } from "@/i18n/I18nProvider";

type Props = {
  label?: string;
  size?: "sm" | "md" | "lg";
  /** Centre the spinner in a tall block, for whole-page loading states. */
  block?: boolean;
};

const SIZES = {
  sm: "h-4 w-4 border-2",
  md: "h-6 w-6 border-2",
  lg: "h-10 w-10 border-[3px]",
} as const;

export default function LoadingSpinner({ label, size = "md", block = false }: Props) {
  const { dict } = useI18n();
  const spinner = (
    <span
      className={`inline-block animate-spin rounded-full border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-zinc-100 ${SIZES[size]}`}
      role="status"
      aria-label={label ?? dict.common.loading}
    />
  );

  if (!block) {
    return (
      <span className="inline-flex items-center gap-2">
        {spinner}
        {label ? (
          <span className="text-sm text-zinc-600 dark:text-zinc-400">{label}</span>
        ) : null}
      </span>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16">
      {spinner}
      {label ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">{label}</p>
      ) : null}
    </div>
  );
}
