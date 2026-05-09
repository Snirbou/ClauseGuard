import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AuthStoreInitializer } from "@/components/auth/AuthStoreInitializer";
import { AUTH_TOKEN_COOKIE, AUTH_USER_COOKIE } from "@/lib/auth-constants";
import type { AuthUser } from "@/store/authStore";

export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const jar = await cookies();
  const token = jar.get(AUTH_TOKEN_COOKIE)?.value;
  if (!token) {
    redirect("/login?next=/my-contracts");
  }

  const userRaw = jar.get(AUTH_USER_COOKIE)?.value;
  let user: AuthUser | null = null;
  if (userRaw) {
    try {
      user = JSON.parse(decodeURIComponent(userRaw)) as AuthUser;
    } catch {
      user = null;
    }
  }

  return (
    <>
      <AuthStoreInitializer user={user} />
      {children}
    </>
  );
}
