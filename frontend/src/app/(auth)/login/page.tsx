"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useForm } from "react-hook-form";

import { FormField } from "@/components/ui/FormField";
import { getAuthMode, login } from "@/lib/auth-service";
import { setAuthToken, setAuthUser } from "@/lib/auth-utils";
import { loginSchema, type LoginValues } from "@/lib/validations/auth";
import { useAuthStore } from "@/store/authStore";

function LoginFormInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    mode: "onTouched",
    defaultValues: { email: "", password: "" },
  });

  const nextPath = searchParams.get("next");
  const mode = getAuthMode();

  async function onSubmit(values: LoginValues) {
    try {
      const result = await login(values.email, values.password);
      setAuthToken(result.token);
      setAuthUser(result.user);
      useAuthStore.getState().setUser(result.user);
      const safeNext =
        nextPath && nextPath.startsWith("/") && !nextPath.startsWith("//")
          ? nextPath
          : "/my-contracts";
      router.push(safeNext);
      router.refresh();
    } catch (e) {
      setError("root.serverError", {
        type: "server",
        message: e instanceof Error ? e.message : "Login failed",
      });
    }
  }

  const serverError = errors.root?.serverError?.message;

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
        Sign in
      </h1>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
        Access your contract analysis and saved work.
      </p>
      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-500">
        Auth mode:{" "}
        <span className="font-mono font-medium text-zinc-700 dark:text-zinc-300">
          {mode}
        </span>
        {mode === "mock" && " — uses a synthetic session for UI development."}
      </p>

      <form
        className="mt-6 space-y-4"
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
        <FormField
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register("email")}
        />
        <FormField
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register("password")}
        />

        {serverError && (
          <div
            role="alert"
            className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300"
          >
            {serverError}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          {isSubmitting ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-zinc-600 dark:text-zinc-400">
        No account?{" "}
        <Link
          href="/signup"
          className="font-medium text-zinc-900 underline underline-offset-2 dark:text-zinc-100"
        >
          Create one
        </Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="text-sm text-zinc-500 dark:text-zinc-400">
          Loading…
        </div>
      }
    >
      <LoginFormInner />
    </Suspense>
  );
}
