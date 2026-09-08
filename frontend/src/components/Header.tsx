"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import LocaleSwitcher from "@/components/LocaleSwitcher";
import { useI18n } from "@/i18n/I18nProvider";
import { useLogout, useSession } from "@/lib/useSession";

const NAV_LINKS = [
  { href: "/", key: "home" },
  { href: "/upload", key: "upload" },
  { href: "/contracts", key: "contracts" },
  { href: "/dashboard", key: "dashboard" },
] as const;

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function Header() {
  const pathname = usePathname();
  const { dict } = useI18n();
  const { user, isLoading } = useSession();
  const logoutMutation = useLogout();

  return (
    <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-zinc-800 dark:bg-black/80">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2 text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-50"
        >
          <span aria-hidden="true">🛡️</span>
          {dict.common.appName}
        </Link>

        {/* Wraps on narrow screens (375px, signed in, Hebrew labels) instead of
            overflowing the viewport horizontally. */}
        <div className="flex flex-wrap items-center justify-end gap-3">
          <nav aria-label={dict.nav.main}>
            <ul className="flex flex-wrap items-center gap-1 text-sm">
              {NAV_LINKS.map((link) => {
                const active = isActive(pathname, link.href);
                return (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      aria-current={active ? "page" : undefined}
                      className={`whitespace-nowrap rounded-lg px-3 py-1.5 font-medium transition-colors ${
                        active
                          ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                          : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-100"
                      }`}
                    >
                      {dict.nav[link.key]}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="flex items-center gap-2 sm:border-s sm:border-zinc-200 sm:ps-3 dark:sm:border-zinc-800">
            <LocaleSwitcher />
            {isLoading ? null : user ? (
              <>
                <span
                  className="hidden max-w-[16ch] truncate text-xs text-zinc-500 dark:text-zinc-400 sm:inline"
                  title={user.email}
                  dir="ltr"
                >
                  {user.email}
                </span>
                <button
                  type="button"
                  onClick={() => logoutMutation.mutate()}
                  disabled={logoutMutation.isPending}
                  className="rounded-lg border border-zinc-300 px-3 py-1.5 text-xs font-semibold text-zinc-600 transition-colors hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
                >
                  {dict.common.signOut}
                </button>
              </>
            ) : (
              <Link
                href="/login"
                className="rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
              >
                {dict.common.signIn}
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
