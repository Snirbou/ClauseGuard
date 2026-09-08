"use client";

import Link from "next/link";
import { useCallback, useRef, useState, type ReactNode } from "react";
import type { UploadResponse, UploadSuccessResponse } from "@/types/contracts";
import { MAX_UPLOAD_BYTES } from "@/types/contracts";
import { formatBytes, uploadContractFile } from "@/lib/api";
import { codedMessage } from "@/i18n";
import { useI18n } from "@/i18n/I18nProvider";
import ClauseList from "@/components/ClauseList";
import ErrorMessage from "@/components/ErrorMessage";
import LoadingSpinner from "@/components/LoadingSpinner";

type Phase = "idle" | "loading" | "success" | "error";

const ACCEPT = "application/pdf,.pdf";

function isPdf(file: File): boolean {
  const type = (file.type || "").toLowerCase();
  return type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

/**
 * Some dictionary sentences embed a verbatim fragment — a filename, or a
 * message the server wrote in English — that must keep left-to-right
 * rendering even inside a Hebrew sentence. Splits the sentence around the
 * fragment so the fragment can carry its own `dir` (and `lang` for English
 * prose). Falls back to the plain sentence if the fragment is not found.
 */
function withLtrFragment(sentence: string, fragment: string, english = false): ReactNode {
  const at = fragment ? sentence.indexOf(fragment) : -1;
  if (at === -1) return sentence;
  return (
    <>
      {sentence.slice(0, at)}
      <span
        dir="ltr"
        lang={english ? "en" : undefined}
        className={english ? "text-start" : undefined}
      >
        {fragment}
      </span>
      {sentence.slice(at + fragment.length)}
    </>
  );
}

export default function UploadDropzone() {
  const { dict } = useI18n();
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState<UploadSuccessResponse | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const fail = useCallback((message: string) => {
    setErrorMessage(message);
    setSuccess(null);
    setPhase("error");
  }, []);

  const onFileSelected = useCallback(
    async (file: File | null) => {
      if (!file) return;

      if (!isPdf(file)) {
        fail(dict.upload.invalidType);
        return;
      }

      // Mirrors the backend's MAX_UPLOAD_BYTES so an oversized file never
      // leaves the browser.
      if (file.size > MAX_UPLOAD_BYTES) {
        fail(dict.upload.tooLarge(formatBytes(file.size), formatBytes(MAX_UPLOAD_BYTES)));
        return;
      }

      if (file.size === 0) {
        fail(dict.upload.empty);
        return;
      }

      setErrorMessage(null);
      setSuccess(null);
      setPhase("loading");

      const result: UploadResponse = await uploadContractFile(file);

      if (result.status === "success") {
        setSuccess(result);
        setPhase("success");
      } else {
        // Known codes get a localized message; unknown ones fall back to the
        // server's English detail.
        fail(codedMessage(dict, result.code, result.detail, dict.upload.uploadFailed));
      }
    },
    [dict, fail],
  );

  const reset = useCallback(() => {
    setPhase("idle");
    setErrorMessage(null);
    setSuccess(null);
  }, []);

  const busy = phase === "loading";

  return (
    <div className="w-full">
      <div
        className={`rounded-xl border-2 border-dashed p-8 transition-colors ${
          dragActive
            ? "border-zinc-900 bg-zinc-100 dark:border-zinc-100 dark:bg-zinc-900"
            : "border-zinc-300 dark:border-zinc-800"
        }`}
        onDragEnter={(e) => {
          e.preventDefault();
          if (!busy) setDragActive(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDragActive(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragActive(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          if (busy) return;
          void onFileSelected(e.dataTransfer.files?.[0] ?? null);
        }}
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <p className="text-4xl" aria-hidden="true">
            📄
          </p>
          <div>
            <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
              {dict.upload.dropTitle}
            </p>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              {dict.upload.dropHint(formatBytes(MAX_UPLOAD_BYTES))}
            </p>
          </div>

          <input
            ref={inputRef}
            id="contract-file"
            type="file"
            accept={ACCEPT}
            className="sr-only"
            disabled={busy}
            onChange={(e) => {
              const picked = e.target.files?.[0] ?? null;
              // Reset first so picking the same file again still fires onChange.
              e.currentTarget.value = "";
              void onFileSelected(picked);
            }}
          />

          <button
            type="button"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
            className="mt-1 inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            {busy ? dict.upload.processing : dict.upload.choose}
          </button>

          {busy ? <LoadingSpinner size="sm" label={dict.upload.extracting} /> : null}
        </div>
      </div>

      {phase === "error" && errorMessage ? (
        <div className="mt-4">
          <ErrorMessage
            title={dict.upload.failedTitle}
            message={errorMessage}
            onRetry={reset}
            retryLabel={dict.upload.startOver}
          />
        </div>
      ) : null}

      {phase === "success" && success ? (
        <div className="mt-6 flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3">
            <div className="text-sm text-emerald-800 dark:text-emerald-200">
              <p className="font-semibold">{dict.upload.successTitle}</p>
              <p className="mt-0.5">
                {withLtrFragment(
                  dict.upload.extracted(success.parsed_clauses.length, success.filename),
                  success.filename,
                )}
                {success.analysis?.status === "started" ? (
                  <>
                    {" "}
                    {dict.upload.analysisStarted}
                  </>
                ) : null}
              </p>
              {success.analysis?.status === "skipped" ? (
                <p className="mt-1 text-xs opacity-80">
                  {/* Known codes render in the UI language; anything else is the
                      server's English reason, kept as an LTR fragment. */}
                  {(() => {
                    const { code, detail } = success.analysis;
                    const text = codedMessage(dict, code, detail, detail);
                    return text === detail
                      ? withLtrFragment(dict.upload.analysisSkipped(text), text, true)
                      : dict.upload.analysisSkipped(text);
                  })()}
                </p>
              ) : null}
            </div>

            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                onClick={reset}
                className="rounded-lg border border-emerald-600/40 px-3 py-1.5 text-xs font-semibold text-emerald-800 transition-colors hover:bg-emerald-500/15 dark:text-emerald-200"
              >
                {dict.upload.uploadAnother}
              </button>
              <Link
                href={`/contracts/${success.contract_id}`}
                className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-emerald-700"
              >
                {dict.upload.analyzeThis}
              </Link>
            </div>
          </div>

          <ClauseList
            filename={success.filename}
            clauses={success.parsed_clauses}
          />
        </div>
      ) : null}
    </div>
  );
}
