import type { Metadata } from "next";
import { Suspense } from "react";
import AuthForm from "@/components/AuthForm";
import LoadingSpinner from "@/components/LoadingSpinner";

export const metadata: Metadata = {
  title: "Create account · ClauseGuard",
  description: "Create a ClauseGuard account to keep your contract analyses.",
};

export default function SignupPage() {
  return (
    <div className="py-8">
      <Suspense fallback={<LoadingSpinner block />}>
        <AuthForm mode="signup" />
      </Suspense>
    </div>
  );
}
