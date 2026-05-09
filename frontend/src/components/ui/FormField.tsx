"use client";

import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

export type FormFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: ReactNode;
  hint?: ReactNode;
  error?: string;
  containerClassName?: string;
};

export const FormField = forwardRef<HTMLInputElement, FormFieldProps>(
  function FormField(
    { label, hint, error, containerClassName, id, name, className, ...rest },
    ref,
  ) {
    const fieldId = id ?? name;
    const errorId = error ? `${String(fieldId)}-error` : undefined;
    const hintId = hint ? `${String(fieldId)}-hint` : undefined;
    const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;

    return (
      <div className={containerClassName}>
        <label
          htmlFor={fieldId}
          className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
        >
          {label}
        </label>
        <input
          ref={ref}
          id={fieldId}
          name={name}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={describedBy}
          className={
            className ??
            "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2 aria-invalid:border-red-500 aria-invalid:ring-red-400 dark:border-zinc-600 dark:bg-zinc-950 dark:text-zinc-50"
          }
          {...rest}
        />
        {hint && !error && (
          <p id={hintId} className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            {hint}
          </p>
        )}
        {error && (
          <p
            id={errorId}
            role="alert"
            className="mt-1 text-xs text-red-600 dark:text-red-400"
          >
            {error}
          </p>
        )}
      </div>
    );
  },
);
