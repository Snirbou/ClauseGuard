import type { Metadata } from "next";
import { Suspense } from "react";
import AuthForm from "@/components/AuthForm";
import LoadingSpinner from "@/components/LoadingSpinner";
import { getServerI18n } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const { dict } = await getServerI18n();
  return { title: dict.meta.login.title, description: dict.meta.login.description };
}

export default function LoginPage() {
  return (
    <div className="py-8">
      {/* useSearchParams (the ?next= redirect) requires a Suspense boundary. */}
      <Suspense fallback={<LoadingSpinner block />}>
        <AuthForm mode="login" />
      </Suspense>
    </div>
  );
}
