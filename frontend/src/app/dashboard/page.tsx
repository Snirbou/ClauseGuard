import type { Metadata } from "next";
import DashboardView from "@/components/DashboardView";
import { getServerI18n } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const { dict } = await getServerI18n();
  return { title: dict.meta.dashboard.title, description: dict.meta.dashboard.description };
}

export default async function DashboardPage() {
  const { dict } = await getServerI18n();
  const t = dict.dashboard;

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t.pageTitle}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          {t.pageLead}
        </p>
      </header>

      <DashboardView />
    </div>
  );
}
