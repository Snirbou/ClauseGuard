/**
 * Locale runtime shared by server and client code.
 *
 * Design: the locale lives in a cookie (`NEXT_LOCALE`), not in the URL, so
 * every route and `proxy.ts` stay exactly as they are. The root layout
 * resolves it (cookie → Accept-Language → English) and sets `<html lang dir>`;
 * client components read the matching dictionary from `I18nProvider`.
 */

import { ApiError } from "@/lib/api";
import { en, type Dictionary } from "./en";
import { he } from "./he";

export type { Dictionary } from "./en";

export const LOCALES = ["en", "he"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_COOKIE = "NEXT_LOCALE";
/** One year, in seconds. */
export const LOCALE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

const RTL_LOCALES: ReadonlySet<Locale> = new Set<Locale>(["he"]);

const DICTIONARIES: Record<Locale, Dictionary> = { en, he };

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

export function isRtl(locale: Locale): boolean {
  return RTL_LOCALES.has(locale);
}

export function getDictionary(locale: Locale): Dictionary {
  return DICTIONARIES[locale];
}

/** BCP 47 tag for Intl APIs (dates, plurals, numbers). */
export function intlLocale(locale: Locale): string {
  return locale === "he" ? "he-IL" : "en-US";
}

/**
 * Pick the locale for a request: explicit cookie first, then the browser's
 * Accept-Language (first supported language wins), else English.
 */
export function resolveLocale(
  cookieValue: string | undefined | null,
  acceptLanguage: string | undefined | null,
): Locale {
  if (isLocale(cookieValue)) return cookieValue;
  if (acceptLanguage) {
    for (const part of acceptLanguage.split(",")) {
      const tag = part.split(";")[0]?.trim().toLowerCase();
      if (!tag) continue;
      const base = tag.split("-")[0];
      if (isLocale(base)) return base;
    }
  }
  return DEFAULT_LOCALE;
}

/**
 * Localized text for a failed API call. Known codes (backend/error_codes.py
 * and the client-side ones in lib/api.ts) map to the dictionary; anything
 * else falls back to the server's English `detail`, then to `fallback`.
 */
/**
 * Localized text for a (code, detail) pair — the rule behind every error
 * the UI shows. The server's own English detail is the most specific text
 * there is (it may name the exact setting to fix), so the English UI keeps
 * it; other locales translate by code and fall back to the detail.
 */
export function codedMessage(
  dict: Dictionary,
  code: string | undefined,
  detail: string | undefined,
  fallback: string,
): string {
  const localized = code ? dict.errors[code] : undefined;
  if (dict.locale !== "en" && localized) return localized;
  if (detail) return detail;
  return localized || fallback;
}

export function apiErrorMessage(dict: Dictionary, err: unknown, fallback: string): string {
  return err instanceof ApiError ? codedMessage(dict, err.code, err.message, fallback) : fallback;
}
