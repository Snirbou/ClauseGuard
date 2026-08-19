import type { Metadata } from "next";
import Link from "next/link";
import ContractsView from "@/components/ContractsView";

export const metadata: Metadata = {
  title: "My contracts · ClauseGuard",
  description: "Every contract you have uploaded, with its analysis status.",
};

export default function ContractsPage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            My contracts
          </h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Select a contract to see its clause-by-clause analysis.
          </p>
        </div>
        <Link
          href="/upload"
          className="inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          Upload
        </Link>
      </header>

      <ContractsView />
    </div>
  );
}
