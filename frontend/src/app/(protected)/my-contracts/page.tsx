import { Suspense } from "react";

import { ContractsList } from "@/components/contracts/ContractsList";
import { ContractsListSkeleton } from "@/components/contracts/ContractsListSkeleton";

export const dynamic = "force-dynamic";

export default function MyContractsPage() {
  return (
    <main className="min-h-screen bg-zinc-50 p-8 font-sans text-zinc-900 dark:bg-black dark:text-zinc-50">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">My contracts</h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Saved analyses, ranked by recency.
          </p>
        </header>

        <Suspense fallback={<ContractsListSkeleton />}>
          <ContractsList />
        </Suspense>
      </div>
    </main>
  );
}
