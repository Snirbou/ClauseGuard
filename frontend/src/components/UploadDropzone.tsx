"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import type { UploadResponse, UploadSuccessResponse } from "@/types/contracts";
import { MAX_UPLOAD_BYTES } from "@/types/contracts";
import { formatBytes, uploadContractFile } from "@/lib/api";
import ClauseList from "@/components/ClauseList";
import ErrorMessage from "@/components/ErrorMessage";
import LoadingSpinner from "@/components/LoadingSpinner";

type Phase = "idle" | "loading" | "success" | "error";

const ACCEPT = "application/pdf,.pdf";

function isPdf(file: File): boolean {
  const type = (file.type || "").toLowerCase();
  return type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

export default function UploadDropzone() {
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
        fail("Invalid file type. Please upload a PDF.");
        return;
      }

      // Mirrors the backend's MAX_UPLOAD_BYTES so an oversized file never
      // leaves the browser.
      if (file.size > MAX_UPLOAD_BYTES) {
        fail(
          `File is too large (${formatBytes(file.size)}). Maximum size is ${formatBytes(
            MAX_UPLOAD_BYTES,
          )}.`,
        );
        return;
      }

      if (file.size === 0) {
        fail("This file is empty.");
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
        fail(result.detail ?? "Upload failed.");
      }
    },
    [fail],
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
              Drop a contract PDF here, or choose a file
            </p>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              PDF only · up to {formatBytes(MAX_UPLOAD_BYTES)}
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
            {busy ? "Processing…" : "Choose PDF"}
          </button>

          {busy ? (
            <LoadingSpinner size="sm" label="Extracting and classifying clauses…" />
          ) : null}
        </div>
      </div>

      {phase === "error" && errorMessage ? (
        <div className="mt-4">
          <ErrorMessage
            title="Upload failed"
            message={errorMessage}
            onRetry={reset}
            retryLabel="Start over"
          />
        </div>
      ) : null}

      {phase === "success" && success ? (
        <div className="mt-6 flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3">
            <div className="text-sm text-emerald-800 dark:text-emerald-200">
              <p className="font-semibold">Uploaded and segmented</p>
              <p className="mt-0.5">
                {success.parsed_clauses.length} clause
                {success.parsed_clauses.length === 1 ? "" : "s"} extracted from{" "}
                {success.filename}.
                {success.analysis?.status === "success"
                  ? ` ${success.analysis.analyzed_count} analyzed automatically.`
                  : null}
              </p>
              {success.analysis?.status === "skipped" ? (
                <p className="mt-1 text-xs opacity-80">
                  Automatic analysis skipped: {success.analysis.detail}
                </p>
              ) : null}
            </div>

            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                onClick={reset}
                className="rounded-lg border border-emerald-600/40 px-3 py-1.5 text-xs font-semibold text-emerald-800 transition-colors hover:bg-emerald-500/15 dark:text-emerald-200"
              >
                Upload another
              </button>
              <Link
                href={`/contracts/${success.contract_id}`}
                className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-emerald-700"
              >
                Analyze this contract →
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
