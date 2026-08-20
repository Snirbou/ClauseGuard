import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Route protection (Next.js 16 proxy — the middleware.ts successor).
 *
 * Optimistic check only: the cookie's *presence* gates navigation so signed-
 * out users land on /login instead of a wall of 401s. Real authorization
 * happens server-side on every API call — a forged cookie gets 401s from
 * FastAPI regardless of what this lets through.
 */

const PROTECTED_PREFIXES = ["/upload", "/contracts", "/dashboard"];
const SESSION_COOKIE = "cg_session";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  if (!isProtected) {
    return NextResponse.next();
  }

  if (request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.next();
  }

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/upload", "/contracts/:path*", "/dashboard"],
};
