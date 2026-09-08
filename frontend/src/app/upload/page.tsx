import type { Metadata } from "next";
import UploadDropzone from "@/components/UploadDropzone";
import { getServerI18n } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const { dict } = await getServerI18n();
  return { title: dict.meta.upload.title, description: dict.meta.upload.description };
}

export default async function UploadPage() {
  const { dict } = await getServerI18n();

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          {dict.upload.pageTitle}
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          {dict.upload.pageLead}
        </p>
      </header>

      <UploadDropzone />
    </div>
  );
}
