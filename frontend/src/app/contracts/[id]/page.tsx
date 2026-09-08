import type { Metadata } from "next";
import ContractDetailView from "@/components/ContractDetailView";
import { getServerI18n } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const { dict } = await getServerI18n();
  return {
    title: dict.meta.contractDetail.title,
    description: dict.meta.contractDetail.description,
  };
}

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
