import type { Metadata } from "next";
import Link from "next/link";
import ContractsView from "@/components/ContractsView";
import { getServerI18n } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const { dict } = await getServerI18n();
  return { title: dict.meta.contracts.title, description: dict.meta.contracts.description };
}

export default async function ContractsPage() {
  const { dict } = await getServerI18n();

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            {dict.contracts.pageTitle}
          </h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            {dict.contracts.pageLead}
          </p>
        </div>
        <Link
          href="/upload"
          className="inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          {dict.common.upload}
        </Link>
      </header>

      <ContractsView />
    </div>
  );
}
