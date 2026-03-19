import UploadDropzone from "@/components/UploadDropzone";

export default function Home() {
  return (
    <main className="min-h-screen bg-zinc-50 p-8 font-sans text-zinc-900 dark:bg-black dark:text-zinc-50">
      <div className="mx-auto flex w-full max-w-3xl flex-col">
        <header className="mt-4">
          <h1 className="text-3xl font-semibold tracking-tight">
            ClauseGuard
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
            Upload a contract PDF to extract and segment text into clauses.
          </p>
        </header>

        <UploadDropzone />
      </div>
    </main>
  );
}
