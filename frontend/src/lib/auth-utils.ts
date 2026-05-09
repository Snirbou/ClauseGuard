import Cookies from "js-cookie";

import type { AuthUser } from "@/store/authStore";

import { AUTH_TOKEN_COOKIE, AUTH_USER_COOKIE } from "./auth-constants";

export { AUTH_TOKEN_COOKIE, AUTH_USER_COOKIE } from "./auth-constants";

const DEFAULT_EXPIRES_DAYS = 7;

export type AuthCookieOptions = Cookies.CookieAttributes;

function defaultCookieOptions(): AuthCookieOptions {
  return {
    path: "/",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
  };
}

/**
 * Persist JWT in a client-readable cookie (Bearer header source).
 * For HttpOnly session cookies later, replace implementation and stop reading in JS.
 */
export function setAuthToken(
  token: string,
  options?: AuthCookieOptions,
): void {
  if (typeof window === "undefined") return;
  Cookies.set(AUTH_TOKEN_COOKIE, token, {
    ...defaultCookieOptions(),
    expires: DEFAULT_EXPIRES_DAYS,
    ...options,
  });
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return Cookies.get(AUTH_TOKEN_COOKIE) ?? null;
}

export function removeAuthToken(): void {
  if (typeof window === "undefined") return;
  Cookies.remove(AUTH_TOKEN_COOKIE, { path: "/" });
}

/**
 * Persist auth user JSON in a client-readable cookie (mirrors Server Component reads).
 */
export function setAuthUser(
  user: AuthUser,
  options?: AuthCookieOptions,
): void {
  if (typeof window === "undefined") return;
  Cookies.set(AUTH_USER_COOKIE, encodeURIComponent(JSON.stringify(user)), {
    ...defaultCookieOptions(),
    expires: DEFAULT_EXPIRES_DAYS,
    ...options,
  });
}

export function getAuthUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = Cookies.get(AUTH_USER_COOKIE);
  if (!raw) return null;
  try {
    return JSON.parse(decodeURIComponent(raw)) as AuthUser;
  } catch {
    return null;
  }
}

export function removeAuthUser(): void {
  if (typeof window === "undefined") return;
  Cookies.remove(AUTH_USER_COOKIE, { path: "/" });
}
