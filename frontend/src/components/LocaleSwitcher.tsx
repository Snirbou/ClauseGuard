"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { useI18n } from "@/i18n/I18nProvider";
import { LOCALE_COOKIE, LOCALE_COOKIE_MAX_AGE, getDictionary, type Locale } from "@/i18n";

/**
 * EN ⇄ HE toggle. Writes the locale cookie and refreshes the server tree;
 * the root layout re-resolves the locale, so `<html lang dir>`, the font and
 * every dictionary string update in the same React commit. Deliberately no
 * optimistic DOM writes: a client-side flip of `<html>` would diverge from
 * the server-resolved locale. `aria-busy` reflects the pending refresh.
 */
export default function LocaleSwitcher() {
  const { locale, dict } = useI18n();
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const next: Locale = locale === "he" ? "en" : "he";
  const nextName = getDictionary(next).languageName;

  function switchLocale() {
    document.cookie = `${LOCALE_COOKIE}=${next}; Path=/; Max-Age=${LOCALE_COOKIE_MAX_AGE}; SameSite=Lax`;
    // router.refresh() re-renders the root layout, which owns <html lang dir>,
    // so content, direction and font switch in the same commit.
    startTransition(() => router.refresh());
  }

  return (
    <button
      type="button"
      onClick={switchLocale}
      aria-busy={pending}
      aria-label={`${dict.common.switchLanguage}: ${nextName}`}
      title={dict.common.switchLanguage}
      className="rounded-lg border border-zinc-300 px-2.5 py-1.5 text-xs font-semibold text-zinc-600 transition-colors hover:bg-zinc-100 aria-busy:opacity-60 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
    >
      {/* Only the endonym is in the other language; the accessible name
          stays in the page language so it is voiced correctly. */}
      <span lang={next}>{nextName}</span>
    </button>
  );
}
