export function ContractsListSkeleton() {
  return (
    <ul className="grid gap-3" aria-busy="true" aria-live="polite">
      {Array.from({ length: 4 }).map((_, i) => (
        <li
          key={i}
          className="h-[68px] animate-pulse rounded-xl border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900"
        />
      ))}
    </ul>
  );
}
