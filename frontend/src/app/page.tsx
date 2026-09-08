import Link from "next/link";
import { getServerI18n } from "@/i18n/server";

export default async function Home() {
  const { dict } = await getServerI18n();
  const t = dict.home;

  return (
    <div className="flex flex-col gap-16">
      <section className="pt-6 sm:pt-12">
        <p className="text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          {t.eyebrow}
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          {t.title}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-zinc-600 dark:text-zinc-400">
          {t.lead}
        </p>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link
            href="/upload"
            className="inline-flex items-center justify-center rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            {t.uploadCta}
          </Link>
          <Link
            href="/contracts"
            className="inline-flex items-center justify-center rounded-lg border border-zinc-300 px-5 py-2.5 text-sm font-semibold text-zinc-800 transition-colors hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:border-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-900"
          >
            {t.viewContracts}
          </Link>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold tracking-tight">{t.howItWorks}</h2>
        <ol className="mt-5 grid gap-4 sm:grid-cols-3">
          {t.steps.map((step, index) => (
            <li
              key={step.title}
              className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-zinc-900 text-xs font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
                {index + 1}
              </span>
              <h3 className="mt-3 font-semibold">{step.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                {step.body}
              </p>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2 className="text-xl font-semibold tracking-tight">{t.riskLevelsTitle}</h2>
        <ul className="mt-5 grid gap-4 sm:grid-cols-3">
          {t.riskExamples.map((risk) => (
            <li
              key={risk.level}
              className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <p className="text-2xl" aria-hidden="true">
                {risk.emoji}
              </p>
              <h3 className="mt-2 font-semibold">{risk.level}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                {risk.body}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="text-lg font-semibold tracking-tight">{t.notTitle}</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          {t.notBody}
        </p>
      </section>
    </div>
  );
}
