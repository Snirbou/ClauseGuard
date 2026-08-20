"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import type { ContractSummary } from "@/types/contracts";
import { ApiError, deleteContract, getContracts } from "@/lib/api";
import ContractCard from "@/components/ContractCard";
import ErrorMessage from "@/components/ErrorMessage";
import LoadingSpinner from "@/components/LoadingSpinner";
import { useRedirectOnAuthError } from "@/lib/useSession";
import { pluralize } from "@/lib/format";

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

export default function ContractsView() {
  const queryClient = useQueryClient();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const contractsQuery = useQuery<ContractSummary[], unknown>({
    queryKey: ["contracts"],
    queryFn: getContracts,
  });

  // A 401 (session expired/revoked mid-session) sends the user to /login
  // instead of a Retry that would just 401 again.
  useRedirectOnAuthError(contractsQuery.error);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteContract(id),
    onSettled: () => {
      setDeletingId(null);
      void queryClient.invalidateQueries({ queryKey: ["contracts"] });
    },
  });

  const onDelete = useCallback(
    (contract: ContractSummary) => {
      const confirmed = window.confirm(
        `Delete "${contract.original_filename}"?\n\nThis permanently removes the contract, its ${contract.clause_count} ${pluralize(
          contract.clause_count,
          "clause",
        )} and any analysis. This cannot be undone.`,
      );
      if (!confirmed) return;
      setDeletingId(contract.id);
      deleteMutation.mutate(contract.id);
    },
    [deleteMutation],
  );

  if (contractsQuery.isPending) {
    return <LoadingSpinner block label="Loading your contracts…" />;
  }

  if (contractsQuery.isError) {
    return (
      <ErrorMessage
        title="Could not load contracts"
        message={errorText(contractsQuery.error, "Could not load your contracts.")}
        onRetry={() => void contractsQuery.refetch()}
      />
    );
  }

  const contracts = contractsQuery.data;

  if (contracts.length === 0) {
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
      {deleteMutation.isError ? (
        <ErrorMessage
          message={errorText(deleteMutation.error, "Could not delete the contract.")}
        />
      ) : null}

      <ul className="flex flex-col gap-3">
        {contracts.map((contract) => (
          <ContractCard
            key={contract.id}
            contract={contract}
            onDelete={onDelete}
            deleting={deletingId === contract.id && deleteMutation.isPending}
          />
        ))}
      </ul>
    </div>
  );
}
