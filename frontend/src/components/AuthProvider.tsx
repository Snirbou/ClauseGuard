"use client";

import { useEffect } from "react";

import { useAuthStore } from "@/store/authStore";

/**
 * Hydrates auth state from cookie + session on the client after SSR.
 */
export default function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const bootstrapAuth = useAuthStore((s) => s.bootstrapAuth);

  useEffect(() => {
    bootstrapAuth();
  }, [bootstrapAuth]);

  return <>{children}</>;
}
