import Link from "next/link";

const STEPS = [
  {
    title: "Upload your PDF",
    body: "Drop in a freelance service agreement. Text is extracted and split into individual clauses.",
  },
  {
    title: "Every clause gets classified",
    body: "Each clause is tagged — payment terms, IP assignment, termination, liability, and more.",
  },
  {
    title: "Read it in plain language",
    body: "The AI pass explains what each clause means for you, lists the specific risk factors, and scores its severity.",
  },
] as const;

const RISK_EXAMPLES = [
  { emoji: "🔴", level: "High", body: "Clauses that could cost you real money or rights." },
  { emoji: "🟡", level: "Medium", body: "Worth negotiating before you sign." },
  { emoji: "🟢", level: "Low", body: "Standard terms with no obvious traps." },
] as const;

export default function Home() {
  return (
    <div className="flex flex-col gap-16">
      <section className="pt-6 sm:pt-12">
        <p className="text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          For freelancers
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          Understand your contract before you sign it.
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-zinc-600 dark:text-zinc-400">
          ClauseGuard reads freelance service agreements clause by clause,
          explains each one in plain English, and flags the terms most likely to
          hurt you — so you know exactly what you are agreeing to.
        </p>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link
            href="/upload"
            className="inline-flex items-center justify-center rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            Upload a contract
          </Link>
          <Link
            href="/contracts"
            className="inline-flex items-center justify-center rounded-lg border border-zinc-300 px-5 py-2.5 text-sm font-semibold text-zinc-800 transition-colors hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:border-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-900"
          >
            View my contracts
          </Link>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold tracking-tight">How it works</h2>
        <ol className="mt-5 grid gap-4 sm:grid-cols-3">
          {STEPS.map((step, index) => (
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
        <h2 className="text-xl font-semibold tracking-tight">
          Risk levels at a glance
        </h2>
        <ul className="mt-5 grid gap-4 sm:grid-cols-3">
          {RISK_EXAMPLES.map((risk) => (
            <li
              key={risk.level}
              className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <p className="text-2xl" aria-hidden="true">
                {risk.emoji}
              </p>
              <h3 className="mt-2 font-semibold">{risk.level} risk</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                {risk.body}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="text-lg font-semibold tracking-tight">
          What ClauseGuard is not
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          ClauseGuard is an educational tool. It spots patterns that commonly
          cause trouble in freelance agreements, but it does not know your
          situation, your jurisdiction, or your negotiating position. It is not
          a lawyer and it does not give legal advice. For anything that matters,
          have a qualified attorney read the contract.
        </p>
      </section>
    </div>
  );
}
