"use client";

import type { Dictionary } from "@/i18n/en";
import { clauseTypeLabel } from "@/lib/format";

/**
 * Row-normalised confusion matrix for the clause classifier (AC §4).
 *
 * Orientation is fixed by the API contract: `matrix[i][j]` counts clauses
 * whose true label is `labels[i]` and whose predicted label is `labels[j]`.
 * Shading is per row, so a bright diagonal cell means high recall for that
 * class and a bright off-diagonal cell names the class it is confused with.
 *
 * The table scrolls inside its own container — with eight classes it is
 * wider than a phone, and the page itself must never scroll sideways.
 */
export default function ConfusionMatrix({
  dict,
  labels,
  matrix,
}: {
  dict: Dictionary;
  labels: string[];
  matrix: number[][];
}) {
  const t = dict.dashboard;
  if (labels.length === 0 || matrix.length === 0) return null;

  return (
    <figure className="mt-5">
      <figcaption className="text-sm font-semibold">{t.confusionTitle}</figcaption>
      <div className="mt-2 w-full overflow-x-auto">
        <table className="w-full min-w-[38rem] border-collapse text-xs">
          <thead>
            <tr>
              <th
                scope="col"
                className="border-b border-zinc-200 p-2 text-start text-[11px] font-semibold whitespace-nowrap text-zinc-500 dark:border-zinc-800 dark:text-zinc-400"
              >
                {t.confusionCorner}
              </th>
              {labels.map((label) => (
                <th
                  key={label}
                  scope="col"
                  className="border-b border-zinc-200 p-2 text-[11px] font-semibold text-zinc-500 dark:border-zinc-800 dark:text-zinc-400"
                >
                  {clauseTypeLabel(dict, label)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, rowIndex) => {
              const trueLabel = labels[rowIndex] ?? String(rowIndex);
              const rowTotal = row.reduce((sum, count) => sum + count, 0);
              return (
                <tr key={trueLabel}>
                  <th
                    scope="row"
                    className="border-b border-zinc-100 p-2 text-start font-medium whitespace-nowrap dark:border-zinc-900"
                  >
                    {clauseTypeLabel(dict, trueLabel)}
                  </th>
                  {row.map((count, colIndex) => {
                    const predictedLabel = labels[colIndex] ?? String(colIndex);
                    const share = rowTotal > 0 ? count / rowTotal : 0;
                    // A faint floor keeps single-clause confusions visible;
                    // the ceiling keeps text legible in both colour schemes.
                    const alpha = count > 0 ? Math.max(0.07, share * 0.6) : 0;
                    return (
                      <td
                        key={`${trueLabel}-${predictedLabel}`}
                        title={t.confusionCellTitle(
                          clauseTypeLabel(dict, trueLabel),
                          clauseTypeLabel(dict, predictedLabel),
                          count,
                          `${Math.round(share * 100)}%`,
                        )}
                        style={{ backgroundColor: `rgba(16, 185, 129, ${alpha})` }}
                        className={`border-b border-zinc-100 p-2 text-center font-mono tabular-nums dark:border-zinc-900 ${
                          rowIndex === colIndex ? "font-bold" : ""
                        } ${count === 0 ? "text-zinc-400 dark:text-zinc-600" : ""}`}
                      >
                        {count}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
        {t.confusionCaption}
      </p>
    </figure>
  );
}
