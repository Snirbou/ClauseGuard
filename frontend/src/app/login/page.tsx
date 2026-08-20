import type { Metadata } from "next";
import { Suspense } from "react";
import AuthForm from "@/components/AuthForm";
import LoadingSpinner from "@/components/LoadingSpinner";

export const metadata: Metadata = {
  title: "Sign in · ClauseGuard",
  description: "Sign in to your ClauseGuard account.",
};

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
