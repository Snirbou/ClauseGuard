"use client";

import { createContext, useContext, useMemo } from "react";
import {
  DEFAULT_LOCALE,
  getDictionary,
  intlLocale,
  isRtl,
  type Dictionary,
  type Locale,
} from "./index";

type I18nValue = {
  locale: Locale;
  dict: Dictionary;
  rtl: boolean;
  /** BCP 47 tag for Intl APIs. */
  intl: string;
};

const I18nContext = createContext<I18nValue | null>(null);

/**
 * Hands the dictionary for the locale the root layout resolved to every
 * client component. Only the locale string crosses the server→client
 * boundary (dictionaries contain functions, which cannot be serialized).
 */
export default function I18nProvider({
  locale,
  children,
}: {
  locale: Locale;
  children: React.ReactNode;
}) {
  const value = useMemo<I18nValue>(
    () => ({
      locale,
      dict: getDictionary(locale),
      rtl: isRtl(locale),
      intl: intlLocale(locale),
    }),
    [locale],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (value) return value;
  // Defensive default so a component rendered outside the provider (tests,
  // isolated previews) still has copy instead of crashing.
  return {
    locale: DEFAULT_LOCALE,
    dict: getDictionary(DEFAULT_LOCALE),
    rtl: false,
    intl: intlLocale(DEFAULT_LOCALE),
  };
}
