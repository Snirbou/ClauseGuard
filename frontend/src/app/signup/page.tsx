import type { Metadata } from "next";
import { Suspense } from "react";
import AuthForm from "@/components/AuthForm";
import LoadingSpinner from "@/components/LoadingSpinner";
import { getServerI18n } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const { dict } = await getServerI18n();
  return { title: dict.meta.signup.title, description: dict.meta.signup.description };
}

export default function SignupPage() {
  return (
    <div className="py-8">
      <Suspense fallback={<LoadingSpinner block />}>
        <AuthForm mode="signup" />
      </Suspense>
    </div>
  );
}
