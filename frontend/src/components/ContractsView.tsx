"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import type { ContractSummary } from "@/types/contracts";
import { deleteContract, getContracts } from "@/lib/api";
import ContractCard from "@/components/ContractCard";
import ErrorMessage from "@/components/ErrorMessage";
import LoadingSpinner from "@/components/LoadingSpinner";
import { apiErrorMessage } from "@/i18n";
import { useI18n } from "@/i18n/I18nProvider";
import { useRedirectOnAuthError } from "@/lib/useSession";

export default function ContractsView() {
  const { dict } = useI18n();
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
        dict.contracts.confirmDelete(contract.original_filename, contract.clause_count),
      );
      if (!confirmed) return;
      setDeletingId(contract.id);
      deleteMutation.mutate(contract.id);
    },
    [deleteMutation, dict],
  );

  if (contractsQuery.isPending) {
    return <LoadingSpinner block label={dict.contracts.loading} />;
  }

  if (contractsQuery.isError) {
    return (
      <ErrorMessage
        title={dict.contracts.loadFailedTitle}
        message={apiErrorMessage(dict, contractsQuery.error, dict.contracts.loadFailed)}
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
        <h2 className="mt-3 font-semibold">{dict.contracts.emptyTitle}</h2>
        <p className="mx-auto mt-1 max-w-sm text-sm text-zinc-600 dark:text-zinc-400">
          {dict.contracts.emptyBody}
        </p>
        <Link
          href="/upload"
          className="mt-5 inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          {dict.contracts.emptyCta}
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
          message={apiErrorMessage(dict, deleteMutation.error, dict.contracts.deleteFailed)}
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
