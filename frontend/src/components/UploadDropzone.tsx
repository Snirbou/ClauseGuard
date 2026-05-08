"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { UploadResponse } from "@/types/contracts";
import { uploadContractFile } from "@/lib/api";

type Phase = "idle" | "loading" | "success" | "error";

export default function UploadDropzone() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fileInputAccept = useMemo(() => "application/pdf,.pdf", []);

  const isBusy = phase === "loading" || phase === "success";

  async function onFileSelected(file: File | null) {
    if (!file) return;

    const fileNameLower = file.name.toLowerCase();
    const isPdfByType =
      (file.type && file.type.toLowerCase() === "application/pdf") ||
      file.type.toLowerCase().endsWith("pdf");
    const isPdfByName = fileNameLower.endsWith(".pdf");

    if (!isPdfByType && !isPdfByName) {
      setErrorMessage("Invalid file type. Please upload a PDF.");
      setPhase("error");
      return;
    }

    setErrorMessage(null);
    setPhase("loading");

    const result: UploadResponse = await uploadContractFile(file);

    if (result.status === "success") {
      setPhase("success");
      router.push(`/results/${result.contract_id}`);
    } else {
      setErrorMessage(result.detail ?? "Upload failed.");
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
          if (isBusy) return;
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
            disabled={isBusy}
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
            {phase === "loading"
              ? "Processing..."
              : phase === "success"
                ? "Redirecting..."
                : "Choose PDF"}
          </label>

          {phase === "error" && (
            <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">
              {errorMessage ?? "Something went wrong."}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
