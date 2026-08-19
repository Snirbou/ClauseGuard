import type { Metadata } from "next";
import ContractDetailView from "@/components/ContractDetailView";

export const metadata: Metadata = {
  title: "Contract analysis · ClauseGuard",
  description: "Clause-by-clause risk analysis for an uploaded contract.",
};

/**
 * `params` is a Promise in Next.js 16 — synchronous access was removed.
 * See node_modules/next/dist/docs/01-app/02-guides/upgrading/version-16.md.
 */
export default async function ContractDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ContractDetailView contractId={id} />;
}
