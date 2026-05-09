"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

import { FormField } from "@/components/ui/FormField";
import { getAuthMode, signup } from "@/lib/auth-service";
import { setAuthToken, setAuthUser } from "@/lib/auth-utils";
import { signupSchema, type SignupValues } from "@/lib/validations/auth";
import { useAuthStore } from "@/store/authStore";

export default function SignupPage() {
  const router = useRouter();

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    mode: "onTouched",
    defaultValues: {
      email: "",
      fullName: "",
      password: "",
      confirmPassword: "",
    },
  });

  const mode = getAuthMode();

  async function onSubmit(values: SignupValues) {
    try {
      const result = await signup({
        email: values.email,
        password: values.password,
        fullName: values.fullName?.trim() || undefined,
      });
      setAuthToken(result.token);
      setAuthUser(result.user);
      useAuthStore.getState().setUser(result.user);
      router.push("/my-contracts");
      router.refresh();
    } catch (e) {
      setError("root.serverError", {
        type: "server",
        message: e instanceof Error ? e.message : "Signup failed",
      });
    }
  }

  const serverError = errors.root?.serverError?.message;

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
        Create account
      </h1>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
        Start analyzing contracts with ClauseGuard.
      </p>
      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-500">
        Auth mode:{" "}
        <span className="font-mono font-medium text-zinc-700 dark:text-zinc-300">
          {mode}
        </span>
      </p>

      <form
        className="mt-6 space-y-4"
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
        <FormField
          label={
            <>
              Full name{" "}
              <span className="font-normal text-zinc-500">(optional)</span>
            </>
          }
          type="text"
          autoComplete="name"
          hint="Optional — helps personalize your workspace."
          error={errors.fullName?.message}
          {...register("fullName")}
        />
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
          autoComplete="new-password"
          error={errors.password?.message}
          {...register("password")}
        />
        <FormField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          error={errors.confirmPassword?.message}
          {...register("confirmPassword")}
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
          {isSubmitting ? "Creating account…" : "Sign up"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-zinc-600 dark:text-zinc-400">
        Already have an account?{" "}
        <Link
          href="/login"
          className="font-medium text-zinc-900 underline underline-offset-2 dark:text-zinc-100"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}
