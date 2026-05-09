"use client";

import { useRef } from "react";

import { useAuthStore, type AuthUser } from "@/store/authStore";

export function AuthStoreInitializer({ user }: { user: AuthUser | null }) {
  const initialized = useRef(false);
  if (typeof window !== "undefined" && !initialized.current) {
    useAuthStore.getState().hydrateFromServer(user);
    initialized.current = true;
  }
  return null;
}
