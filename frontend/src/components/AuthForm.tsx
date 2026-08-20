"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, login, register } from "@/lib/api";
import ErrorMessage from "@/components/ErrorMessage";
import LoadingSpinner from "@/components/LoadingSpinner";

const MIN_PASSWORD_LENGTH = 8;

type Props = {
  mode: "login" | "signup";
};

const COPY = {
  login: {
    title: "Welcome back",
    subtitle: "Sign in to see your contracts and analyses.",
    submit: "Sign in",
    switchText: "New to ClauseGuard?",
    switchHref: "/signup",
    switchLabel: "Create an account",
  },
  signup: {
    title: "Create your account",
    subtitle: "Your contracts and analyses stay private to your account.",
    submit: "Create account",
    switchText: "Already have an account?",
    switchHref: "/login",
    switchLabel: "Sign in",
  },
} as const;

export default function AuthForm({ mode }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const copy = COPY[mode];

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    const trimmedEmail = email.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(trimmedEmail)) {
      setError("Enter a valid email address.");
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }

    setSubmitting(true);
    try {
      const action = mode === "signup" ? register : login;
      const user = await action(trimmedEmail, password);
      queryClient.setQueryData(["session"], user);
      const next = searchParams.get("next");
      // Only follow same-app relative paths — never external redirects.
      router.push(next && next.startsWith("/") && !next.startsWith("//") ? next : "/contracts");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Please try again.",
      );
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md">
      <header className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          {copy.title}
        </h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          {copy.subtitle}
        </p>
      </header>

      <form
        onSubmit={onSubmit}
        className="mt-8 flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
      >
        {error ? <ErrorMessage message={error} /> : null}

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="auth-email"
            className="text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400"
          >
            Email
          </label>
          <input
            id="auth-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none transition-colors focus:border-zinc-500 focus-visible:ring-2 focus-visible:ring-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            placeholder="you@example.com"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="auth-password"
            className="text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400"
          >
            Password
          </label>
          <input
            id="auth-password"
            type="password"
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            required
            minLength={MIN_PASSWORD_LENGTH}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none transition-colors focus:border-zinc-500 focus-visible:ring-2 focus-visible:ring-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            placeholder={mode === "signup" ? `At least ${MIN_PASSWORD_LENGTH} characters` : "Your password"}
          />
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="mt-2 inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          {submitting ? (
            <>
              <LoadingSpinner size="sm" />
              {mode === "signup" ? "Creating account…" : "Signing in…"}
            </>
          ) : (
            copy.submit
          )}
        </button>
      </form>

      <p className="mt-4 text-center text-sm text-zinc-600 dark:text-zinc-400">
        {copy.switchText}{" "}
        <Link
          href={copy.switchHref}
          className="font-semibold text-zinc-900 underline underline-offset-2 dark:text-zinc-100"
        >
          {copy.switchLabel}
        </Link>
      </p>
    </div>
  );
}
