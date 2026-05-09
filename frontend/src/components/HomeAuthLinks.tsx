"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuthStore } from "@/store/authStore";

export default function HomeAuthLinks() {
  const router = useRouter();
  const { isAuthenticated, isHydrated, logout, user } = useAuthStore();

  if (!isHydrated) {
    return (
      <div className="text-xs text-zinc-400 dark:text-zinc-500">Loading…</div>
    );
  }

  if (isAuthenticated) {
    return (
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {user?.email && (
          <span className="text-zinc-600 dark:text-zinc-400">{user.email}</span>
        )}
        <Link
          href="/my-contracts"
          className="font-medium text-zinc-700 underline underline-offset-2 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-white"
        >
          My contracts
        </Link>
        <button
          type="button"
          onClick={() => {
            logout();
            router.refresh();
          }}
          className="font-medium text-zinc-700 underline underline-offset-2 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-white"
        >
          Log out
        </button>
      </div>
    );
  }

  return (
    <Link
      href="/login"
      className="text-sm font-medium text-zinc-700 underline underline-offset-2 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-white"
    >
      Sign in
    </Link>
  );
}
