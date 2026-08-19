import type { Metadata } from "next";
import UploadDropzone from "@/components/UploadDropzone";

export const metadata: Metadata = {
  title: "Upload a contract · ClauseGuard",
  description: "Upload a freelance service agreement PDF for clause extraction and risk analysis.",
};

export default function UploadPage() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Upload a contract
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          Your PDF is parsed into individual clauses and each one is classified.
          Nothing is sent to the AI model until you start the analysis on the
          next screen.
        </p>
      </header>

      <UploadDropzone />
    </div>
  );
}
