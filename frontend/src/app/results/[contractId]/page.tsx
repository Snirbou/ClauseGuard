import ResultsView from "@/components/ResultsView";

export default async function ResultsPage({
  params,
}: {
  params: Promise<{ contractId: string }>;
}) {
  const { contractId } = await params;

  return (
    <main className="min-h-screen bg-zinc-50 p-8 font-sans text-zinc-900 dark:bg-black dark:text-zinc-50">
      <div className="mx-auto flex w-full max-w-3xl flex-col">
        <header className="mt-4">
          <h1 className="text-3xl font-semibold tracking-tight">
            ClauseGuard
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
            Contract analysis
          </p>
        </header>

        <ResultsView contractId={contractId} />
      </div>
    </main>
  );
}
