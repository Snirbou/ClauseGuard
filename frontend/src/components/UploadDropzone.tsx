"use client";

import { useMemo, useState } from "react";
import type {
  ParsedClause,
  UploadResponse,
  UploadSuccessResponse,
} from "@/types/contracts";
import { uploadContractFile } from "@/lib/api";
import ClauseList from "@/components/ClauseList";

type Phase = "idle" | "loading" | "success" | "error";

export default function UploadDropzone() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState<UploadSuccessResponse | null>(null);

  const fileInputAccept = useMemo(() => "application/pdf,.pdf", []);

  async function onFileSelected(file: File | null) {
    if (!file) return;

    const fileNameLower = file.name.toLowerCase();
    const isPdfByType =
      (file.type && file.type.toLowerCase() === "application/pdf") ||
      file.type.toLowerCase().endsWith("pdf");
    const isPdfByName = fileNameLower.endsWith(".pdf");

    if (!isPdfByType && !isPdfByName) {
      setErrorMessage("Invalid file type. Please upload a PDF.");
      setSuccess(null);
      setPhase("error");
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
      setErrorMessage(result.detail ?? "Upload failed.");
      setSuccess(null);
      setPhase("error");
    }
  }

  return (
    <div className="w-full max-w-3xl">
      <div
        className="mt-8 rounded-xl border-2 border-dashed border-zinc-300 p-6 text-zinc-700 dark:border-zinc-800 dark:text-zinc-200"
        onDragOver={(e) => {
          e.preventDefault();
        }}
        onDrop={(e) => {
          e.preventDefault();
          if (phase === "loading") return;
          const dropped = e.dataTransfer.files?.[0] ?? null;
          void onFileSelected(dropped);
        }}
      >
        <div className="flex flex-col gap-3">
          <div className="text-sm font-semibold">
            Drop a PDF here, or choose a file.
          </div>

          <input
            id="contract-file"
            type="file"
            accept={fileInputAccept}
            className="hidden"
            disabled={phase === "loading"}
            onChange={(e) => {
              const picked = e.target.files?.[0] ?? null;
              void onFileSelected(picked);
              // allow selecting the same file again
              e.currentTarget.value = "";
            }}
          />

          <label
            htmlFor="contract-file"
            className="inline-flex cursor-pointer items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {phase === "loading" ? "Processing..." : "Choose PDF"}
          </label>

          {phase === "error" && (
            <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">
              {errorMessage ?? "Something went wrong."}
            </div>
          )}
        </div>
      </div>

      {phase === "success" && success && (
        <ClauseList
          filename={success.filename}
          clauses={success.parsed_clauses as ParsedClause[]}
        />
      )}
    </div>
  );
}

