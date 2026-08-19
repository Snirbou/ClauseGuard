type Props = {
  message: string;
  title?: string;
  onRetry?: () => void;
  retryLabel?: string;
};

export default function ErrorMessage({
  message,
  title,
  onRetry,
  retryLabel = "Try again",
}: Props) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-800 dark:text-red-200"
    >
      {title ? <p className="font-semibold">{title}</p> : null}
      <p className={title ? "mt-1" : undefined}>{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center rounded-lg border border-red-500/40 px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-red-500/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}
