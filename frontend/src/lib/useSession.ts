"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import type { UserInfo } from "@/types/contracts";
import { getSession, logout } from "@/lib/api";

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
