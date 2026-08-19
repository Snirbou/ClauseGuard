"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type { ContractSummary } from "@/types/contracts";
import { ApiError, deleteContract, getContracts } from "@/lib/api";
import ContractCard from "@/components/ContractCard";
import ErrorMessage from "@/components/ErrorMessage";
import LoadingSpinner from "@/components/LoadingSpinner";
import { pluralize } from "@/lib/format";

export default function ContractsView() {
  const [contracts, setContracts] = useState<ContractSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setContracts(null);
    try {
      setContracts(await getContracts());
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not load your contracts.",
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onDelete = useCallback(async (contract: ContractSummary) => {
    const confirmed = window.confirm(
      `Delete "${contract.original_filename}"?\n\nThis permanently removes the contract, its ${contract.clause_count} ${pluralize(
        contract.clause_count,
        "clause",
      )} and any analysis. This cannot be undone.`,
    );
    if (!confirmed) return;

    setDeletingId(contract.id);
    setError(null);
    try {
      await deleteContract(contract.id);
      setContracts((current) =>
        current ? current.filter((item) => item.id !== contract.id) : current,
      );
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not delete the contract.",
      );
    } finally {
      setDeletingId(null);
    }
  }, []);

  if (contracts === null && !error) {
    return <LoadingSpinner block label="Loading your contracts…" />;
  }

  if (error && contracts === null) {
    return <ErrorMessage title="Could not load contracts" message={error} onRetry={() => void load()} />;
  }

  if (contracts && contracts.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-300 py-16 text-center dark:border-zinc-800">
        <p className="text-3xl" aria-hidden="true">
          📂
        </p>
        <h2 className="mt-3 font-semibold">No contracts yet</h2>
        <p className="mx-auto mt-1 max-w-sm text-sm text-zinc-600 dark:text-zinc-400">
          Upload a freelance service agreement to get a clause-by-clause
          breakdown.
        </p>
        <Link
          href="/upload"
          className="mt-5 inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          Upload your first contract
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* A delete that fails after the list has loaded shows inline rather
          than replacing the whole list. */}
      {error ? <ErrorMessage message={error} /> : null}

      <ul className="flex flex-col gap-3">
        {contracts?.map((contract) => (
          <ContractCard
            key={contract.id}
            contract={contract}
            onDelete={onDelete}
            deleting={deletingId === contract.id}
          />
        ))}
      </ul>
    </div>
  );
}
