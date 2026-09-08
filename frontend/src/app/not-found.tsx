import Link from "next/link";
import { getServerI18n } from "@/i18n/server";

export default async function NotFound() {
  const { dict } = await getServerI18n();

  return (
    <div className="py-16 text-center">
      <p className="text-3xl" aria-hidden="true">
        🔍
      </p>
      <h1 className="mt-3 text-xl font-semibold tracking-tight">{dict.notFound.title}</h1>
      <p className="mx-auto mt-2 max-w-md text-sm text-zinc-600 dark:text-zinc-400">
        {dict.notFound.body}
      </p>
      <Link
        href="/"
        className="mt-6 inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
      >
        {dict.notFound.backHome}
      </Link>
    </div>
  );
}
