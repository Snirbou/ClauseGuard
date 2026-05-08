type Props = {
  text: string;
};

export default function DisclaimerBanner({ text }: Props) {
  return (
    <div
      role="note"
      aria-label="Informational disclaimer"
      className="sticky top-0 z-10 -mx-4 mb-4 border-b border-amber-300 bg-amber-50 px-4 py-2 text-xs leading-relaxed text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-200"
    >
      <span className="font-semibold">Informational analysis only. </span>
      {text}
    </div>
  );
}
