/**
 * Server-side locale resolution (layouts, pages, generateMetadata).
 *
 * Reading cookies/headers opts the route into dynamic rendering, which is
 * fine: the app runs on a Node server (Railway / docker), not as a static
 * export, and the pages are personal anyway.
 */

import { cookies, headers } from "next/headers";
import {
  LOCALE_COOKIE,
  getDictionary,
  isRtl,
  resolveLocale,
  type Dictionary,
  type Locale,
} from "./index";

export async function getServerLocale(): Promise<Locale> {
  const cookieStore = await cookies();
  const headerList = await headers();
  return resolveLocale(
    cookieStore.get(LOCALE_COOKIE)?.value,
    headerList.get("accept-language"),
  );
}

export async function getServerI18n(): Promise<{
  locale: Locale;
  dict: Dictionary;
  rtl: boolean;
}> {
  const locale = await getServerLocale();
  return { locale, dict: getDictionary(locale), rtl: isRtl(locale) };
}
