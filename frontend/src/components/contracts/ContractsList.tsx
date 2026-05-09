import Link from "next/link";

import { fetchUserContractsServer } from "@/lib/api-server";

export async function ContractsList() {
  const items = await fetchUserContractsServer();

  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-300 p-8 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
        No contracts yet. Upload one from the home page to get started.
      </div>
    );
  }

  return (
    <ul className="grid gap-3">
      {items.map((c) => (
        <li
          key={c.contract_id}
          className="rounded-xl border border-zinc-200 bg-white p-4 transition hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900"
        >
          <Link href={`/results/${c.contract_id}`} className="block">
            <p className="text-sm font-medium">{c.filename}</p>
            <p className="mt-1 text-xs text-zinc-500">
              {new Date(c.created_at).toLocaleString()} · {c.clause_count}{" "}
              clauses
            </p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
