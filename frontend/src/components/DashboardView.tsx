"use client";

import { useQuery } from "@tanstack/react-query";
import type { MetricsResponse } from "@/types/contracts";
import { getMetrics } from "@/lib/api";
import ErrorMessage from "@/components/ErrorMessage";
import LoadingSpinner from "@/components/LoadingSpinner";
import { apiErrorMessage } from "@/i18n";
import { useI18n } from "@/i18n/I18nProvider";
import { clauseTypeLabel } from "@/lib/format";
import { useRedirectOnAuthError } from "@/lib/useSession";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        {label}
      </dt>
      <dd className="mt-1 text-2xl font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

function F1Bar({ label, value }: { label: string; value: number }) {
  const percent = Math.round(value * 100);
  const target = value >= 0.85;
  return (
    <div className="flex items-center gap-3">
      <span className="w-40 shrink-0 truncate text-sm text-zinc-700 dark:text-zinc-300">
        {label}
      </span>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-900">
        <div
          className={`h-full rounded-full ${target ? "bg-emerald-500" : "bg-amber-500"}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="w-14 shrink-0 text-end font-mono text-sm tabular-nums">
        {value.toFixed(3)}
      </span>
    </div>
  );
}

/**
 * The evaluation dashboard the PRD's acceptance criteria call for (§4):
 * classifier quality per class, pipeline latency, active model versions,
 * and UPL compliance counters.
 */
export default function DashboardView() {
  const { dict } = useI18n();
  const t = dict.dashboard;

  const metricsQuery = useQuery<MetricsResponse, unknown>({
    queryKey: ["metrics"],
    queryFn: getMetrics,
  });

  useRedirectOnAuthError(metricsQuery.error);

  if (metricsQuery.isPending) {
    return <LoadingSpinner block label={t.loading} />;
  }

  if (metricsQuery.isError) {
    return (
      <ErrorMessage
        title={t.loadFailedTitle}
        message={apiErrorMessage(dict, metricsQuery.error, t.loadFailed)}
        onRetry={() => void metricsQuery.refetch()}
      />
    );
  }

  const { classifier, runs, pipeline, compliance } = metricsQuery.data;
  const perClass = Object.entries(classifier.per_class_f1 ?? {}).filter(
    ([key]) => !key.includes("avg"),
  );

  return (
    <div className="flex flex-col gap-8">
      <section aria-label={t.pipeline}>
        <h2 className="text-lg font-semibold tracking-tight">{t.pipeline}</h2>
        <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat
            label={t.classifier}
            value={classifier.mode === "model" ? t.trainedModel : t.keywordFallback}
          />
          <Stat label={t.llmProvider} value={`${pipeline.provider}/${pipeline.model}`} />
          <Stat label={t.concurrency} value={pipeline.concurrency} />
          <Stat label={t.retries} value={pipeline.max_retries} />
        </dl>
        {classifier.load_error ? (
          <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
            {t.loadIssue}{" "}
            <span dir="ltr" lang="en">
              {classifier.load_error}
            </span>
          </p>
        ) : null}
      </section>

      {classifier.test_macro_f1 ? (
        <section aria-label={t.qualityTitle}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold tracking-tight">{t.qualityTitle}</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              {t.trainedMeta(
                classifier.artifact ?? "",
                classifier.trained_at_utc?.slice(0, 10) ?? "",
                classifier.sklearn_version_trained ?? "",
              )}
            </p>
          </div>
          <div className="mt-3 rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex items-baseline justify-between">
              <p className="text-sm font-semibold">
                {t.macroF1}{" "}
                <span className="font-mono tabular-nums">
                  {classifier.test_macro_f1.toFixed(3)}
                </span>
              </p>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">{t.target}</p>
            </div>
            <div className="mt-4 flex flex-col gap-2.5">
              {perClass.map(([label, value]) => (
                <F1Bar key={label} label={clauseTypeLabel(dict, label)} value={value} />
              ))}
            </div>
          </div>
        </section>
      ) : (
        <section>
          <h2 className="text-lg font-semibold tracking-tight">{t.qualityTitle}</h2>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{t.noModelBody}</p>
        </section>
      )}

      <section aria-label={t.runsTitle}>
        <h2 className="text-lg font-semibold tracking-tight">{t.runsTitle}</h2>
        <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Stat label={t.total} value={runs.total} />
          <Stat label={t.completed} value={runs.completed} />
          <Stat label={t.failed} value={runs.failed} />
          <Stat label={t.p50} value={runs.p50_ms != null ? `${runs.p50_ms}ms` : "—"} />
          <Stat label={t.p95} value={runs.p95_ms != null ? `${runs.p95_ms}ms` : "—"} />
        </dl>
        <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{t.runsHint}</p>
      </section>

      <section aria-label={t.complianceTitle}>
        <h2 className="text-lg font-semibold tracking-tight">{t.complianceTitle}</h2>
        <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label={t.disclaimerViews} value={compliance.disclaimer_views_logged} />
        </dl>
      </section>
    </div>
  );
}
