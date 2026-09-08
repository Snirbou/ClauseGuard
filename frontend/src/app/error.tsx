"use client";

import { useEffect } from "react";
import { useI18n } from "@/i18n/I18nProvider";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { dict } = useI18n();

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="py-16 text-center">
      <p className="text-3xl" aria-hidden="true">
        ⚠️
      </p>
      <h1 className="mt-3 text-xl font-semibold tracking-tight">{dict.errorPage.title}</h1>
      <p className="mx-auto mt-2 max-w-md text-sm text-zinc-600 dark:text-zinc-400">
        {error.message ? (
          // Runtime error text is whatever was thrown — English, never localized.
          <span dir="ltr" lang="en">
            {error.message}
          </span>
        ) : (
          dict.errorPage.fallback
        )}
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-6 inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
      >
        {dict.common.tryAgain}
      </button>
    </div>
  );
}
