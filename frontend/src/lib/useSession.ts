"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import type { UserInfo } from "@/types/contracts";
import { ApiError, getSession, logout } from "@/lib/api";

/**
 * The signed-in user, resolved from the httpOnly session cookie via
 * GET /api/auth/me. `null` means "definitely signed out"; `undefined`
 * means the check is still in flight.
 */
export function useSession() {
  const query = useQuery<UserInfo | null>({
    queryKey: ["session"],
    queryFn: getSession,
    staleTime: 60_000,
    retry: false,
  });

  return {
    user: query.data ?? null,
    isLoading: query.isPending,
  };
}

/** Sign out, drop every cached query (they are all user-scoped), go home. */
export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear();
      router.push("/");
      router.refresh();
    },
  });
}

/**
 * Redirect to /login when a data query fails with 401 (session revoked or
 * expired while the tab stayed open). Without this the data views show a
 * Retry that just 401s again — a dead-end. Clears the stale session/cache
 * first so the header and any cached data reset.
 */
export function useRedirectOnAuthError(error: unknown): void {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      queryClient.clear();
      const next = pathname ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${next}`);
    }
  }, [error, router, pathname, queryClient]);
}
