"use client";

import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import type { MetricsResponse } from "@/types/contracts";
import { getMetrics } from "@/lib/api";
import ConfusionMatrix from "@/components/ConfusionMatrix";
import ErrorMessage from "@/components/ErrorMessage";
import LoadingSpinner from "@/components/LoadingSpinner";
import { apiErrorMessage } from "@/i18n";
import { useI18n } from "@/i18n/I18nProvider";
import { clauseTypeLabel, formatDateTime } from "@/lib/format";
import { useRedirectOnAuthError } from "@/lib/useSession";

/** Placeholder for a metric the server has not measured yet. */
const DASH = "—";

const TH =
  "border-b border-zinc-200 px-2 py-2 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:border-zinc-800 dark:text-zinc-400";
const TD = "border-b border-zinc-100 px-2 py-2 dark:border-zinc-900";
const NUM = "font-mono tabular-nums";

function num(value: number | null | undefined, digits = 3): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : DASH;
}

function pct(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(value * 100)}%`
    : DASH;
}

function joinVersion(name?: string, version?: string): string | null {
  if (!name) return null;
  return version ? `${name} ${version}` : name;
}

/**
 * English identifiers — model names, shas, file paths, prompt text — keep
 * their own direction so they stay readable inside the Hebrew (RTL) layout.
 */
function Ltr({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span dir="ltr" lang="en" className={className}>
      {children}
    </span>
  );
}

function Stat({
  label,
  value,
  size = "lg",
  ltr = false,
}: {
  label: string;
  value: ReactNode;
  /** "sm" is for identifiers and version strings, which do not fit at 2xl. */
  size?: "lg" | "sm";
  ltr?: boolean;
}) {
  const ltrProps = ltr ? { dir: "ltr" as const, lang: "en" } : {};
  const valueClass =
    size === "sm" ? `text-sm break-words${ltr ? " font-mono" : ""}` : "text-2xl";
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        {label}
      </dt>
      <dd {...ltrProps} className={`mt-1 font-semibold tabular-nums ${valueClass}`}>
        {value}
      </dd>
    </div>
  );
}

/**
 * A 0–1 score against its PRD target. The default is the classifier's
 * AC-C02 target (0.850); the risk bars pass their own AC-R05 targets.
 */
function F1Bar({ label, value, target = 0.85 }: { label: string; value: number; target?: number }) {
  const percent = Math.round(value * 100);
  const met = value >= target;
  return (
    <div className="flex items-center gap-3">
      <span className="w-40 shrink-0 truncate text-sm text-zinc-700 dark:text-zinc-300">
        {label}
      </span>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-900">
        <div
          className={`h-full rounded-full ${met ? "bg-emerald-500" : "bg-amber-500"}`}
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
 * classifier quality per class (plus a held-out report and confusion
 * matrix), summary readability (AC-P04), high-risk precision/recall
 * (AC-R05), pipeline latency including p99, the active ML and DSPy program
 * versions, DSPy optimizer history, and the UPL compliance counters.
 *
 * Every block beyond the original four is optional on the wire, so each
 * section renders its own placeholder rather than assuming the field exists.
 */
export default function DashboardView() {
  const { dict, intl } = useI18n();
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

  const { classifier, runs, pipeline, compliance, quality, risk } = metricsQuery.data;
  const perClass = Object.entries(classifier.per_class_f1 ?? {}).filter(
    ([key]) => !key.includes("avg"),
  );

  // --- Model versions -----------------------------------------------------
  const program = pipeline.dspy_program;
  const programSha = program?.artifact_sha ? program.artifact_sha.slice(0, 12) : null;
  const spacyTrained = joinVersion(
    classifier.spacy_model_trained,
    classifier.spacy_model_version_trained,
  );
  const spacyRuntime = joinVersion(
    classifier.spacy_model_runtime ?? classifier.spacy_model_configured,
    classifier.spacy_model_version_runtime,
  );

  // --- Held-out evaluation ------------------------------------------------
  const evaluation = classifier.eval;
  const evalLabels = evaluation?.labels?.length
    ? evaluation.labels
    : Object.keys(evaluation?.per_class ?? {});
  const evalRows = evalLabels
    .filter((key) => !key.includes("avg") && key !== "accuracy")
    .flatMap((key) => {
      const metrics = evaluation?.per_class?.[key];
      return metrics ? [{ key, metrics }] : [];
    });

  // --- Readability (AC-P04) and high-risk detection (AC-R05) --------------
  const readability = quality?.readability;
  const riskTargets = {
    precision: risk?.targets?.precision ?? 0.75,
    recall: risk?.targets?.recall ?? 0.7,
  };
  const riskTargetLine = t.riskTargets(num(riskTargets.precision, 2), num(riskTargets.recall, 2));

  // --- DSPy optimizer history --------------------------------------------
  const history = pipeline.optimizer_history;
  const optimizerRuns = history?.runs ?? [];
  const trials = history?.latest?.trials ?? [];

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
            {t.loadIssue} <Ltr>{classifier.load_error}</Ltr>
          </p>
        ) : null}
      </section>

      <section aria-label={t.versionsTitle}>
        <h2 className="text-lg font-semibold tracking-tight">{t.versionsTitle}</h2>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{t.versionsHint}</p>
        <dl className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Stat size="sm" ltr label={t.classifierArtifact} value={classifier.artifact ?? DASH} />
          <Stat size="sm" ltr label={t.spacyTrained} value={spacyTrained ?? DASH} />
          <Stat size="sm" ltr label={t.spacyRuntime} value={spacyRuntime ?? DASH} />
          <Stat size="sm" ltr label={t.dspyVersion} value={program?.dspy_version ?? DASH} />
          <Stat size="sm" ltr label={t.pipelineVersion} value={program?.pipeline_version ?? DASH} />
          <Stat
            size="sm"
            label={t.dspyProgram}
            value={
              !program ? (
                DASH
              ) : program.optimized ? (
                <>
                  {t.programOptimized}
                  {programSha ? (
                    <>
                      {" · "}
                      <Ltr className="font-mono">{programSha}</Ltr>
                    </>
                  ) : null}
                </>
              ) : (
                t.programUnoptimized
              )
            }
          />
          <Stat
            size="sm"
            ltr
            label={t.llmProvider}
            value={`${pipeline.provider}/${pipeline.model}`}
          />
        </dl>
      </section>

      <section aria-label={t.qualityTitle}>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-semibold tracking-tight">{t.qualityTitle}</h2>
          {classifier.test_macro_f1 ? (
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              {t.trainedMeta(
                classifier.artifact ?? "",
                classifier.trained_at_utc?.slice(0, 10) ?? "",
                classifier.sklearn_version_trained ?? "",
              )}
            </p>
          ) : null}
        </div>

        {classifier.test_macro_f1 ? (
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
            <p className="mt-4 text-xs text-zinc-500 dark:text-zinc-400">{t.holdoutNote}</p>
          </div>
        ) : (
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{t.noModelBody}</p>
        )}

        {evaluation ? (
          <div className="mt-4 rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-sm font-semibold">{t.evalTitle}</h3>
              <p
                dir="ltr"
                lang="en"
                className="font-mono text-xs text-zinc-500 dark:text-zinc-400"
              >
                {t.evalMeta(
                  evaluation.dataset,
                  evaluation.split,
                  evaluation.n,
                  joinVersion(evaluation.spacy_model, evaluation.spacy_model_version) ?? "",
                )}
              </p>
            </div>

            <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label={t.evalMacroF1} value={num(evaluation.macro_f1)} />
              <Stat label={t.evalServedMacroF1} value={num(evaluation.served_macro_f1)} />
              <Stat
                label={t.evalThreshold}
                value={num(evaluation.low_confidence_threshold, 2)}
              />
              <Stat label={t.evalSampleSize} value={evaluation.n ?? DASH} />
            </dl>

            {evalRows.length > 0 ? (
              <div className="mt-5 w-full overflow-x-auto">
                <table className="w-full min-w-[30rem] border-collapse text-sm">
                  <thead>
                    <tr>
                      <th scope="col" className={`${TH} text-start`}>
                        {t.colClass}
                      </th>
                      <th scope="col" className={`${TH} text-end`}>
                        {t.colPrecision}
                      </th>
                      <th scope="col" className={`${TH} text-end`}>
                        {t.colRecall}
                      </th>
                      <th scope="col" className={`${TH} text-end`}>
                        {t.colF1}
                      </th>
                      <th scope="col" className={`${TH} text-end`}>
                        {t.colSupport}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {evalRows.map(({ key, metrics }) => (
                      <tr key={key}>
                        <th scope="row" className={`${TD} text-start font-medium`}>
                          {clauseTypeLabel(dict, key)}
                        </th>
                        <td className={`${TD} ${NUM} text-end`}>{num(metrics.precision)}</td>
                        <td className={`${TD} ${NUM} text-end`}>{num(metrics.recall)}</td>
                        <td className={`${TD} ${NUM} text-end`}>{num(metrics.f1)}</td>
                        <td className={`${TD} ${NUM} text-end`}>{metrics.support}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            {/* The matrix is indexed by `eval.labels`, so it must be read in
                that order — never the per-class key order. */}
            <ConfusionMatrix
              dict={dict}
              labels={evaluation.labels ?? []}
              matrix={evaluation.confusion_matrix ?? []}
            />

            {evaluation.note ? (
              <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
                <Ltr>{evaluation.note}</Ltr>
              </p>
            ) : null}
            {evaluation.generated_at ? (
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                {t.evalGenerated(formatDateTime(evaluation.generated_at, intl))}
              </p>
            ) : null}
          </div>
        ) : null}
      </section>

      <section aria-label={t.readabilityTitle}>
        <h2 className="text-lg font-semibold tracking-tight">{t.readabilityTitle}</h2>
        {readability && readability.sample_size > 0 ? (
          <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label={t.readabilityAvg} value={num(readability.avg_grade, 1)} />
            <Stat label={t.readabilityMedian} value={num(readability.median_grade, 1)} />
            <Stat label={t.readabilityShare} value={pct(readability.share_at_or_below_target)} />
            <Stat label={t.readabilitySample} value={readability.sample_size} />
          </dl>
        ) : (
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{t.readabilityEmpty}</p>
        )}
        <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
          {t.readabilityTarget(readability?.target_grade ?? 12)}
        </p>
      </section>

      <section aria-label={t.riskTitle}>
        <h2 className="text-lg font-semibold tracking-tight">{t.riskTitle}</h2>
        <div className="mt-3 rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
          {risk?.measured ? (
            <>
              <div className="flex flex-col gap-2.5">
                <F1Bar
                  label={t.riskPrecision}
                  value={risk.precision_high ?? 0}
                  target={riskTargets.precision}
                />
                <F1Bar
                  label={t.riskRecall}
                  value={risk.recall_high ?? 0}
                  target={riskTargets.recall}
                />
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label={t.riskF1} value={num(risk.f1_high)} />
                <Stat label={t.riskSample} value={risk.n ?? DASH} />
                <Stat label={t.riskThreshold} value={num(risk.threshold_high, 2)} />
                <Stat
                  size="sm"
                  ltr
                  label={t.llmProvider}
                  value={`${risk.provider ?? DASH}/${risk.model ?? DASH}`}
                />
              </dl>
              <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">{riskTargetLine}</p>
              {risk.generated_at ? (
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  {t.riskGenerated(formatDateTime(risk.generated_at, intl))}
                </p>
              ) : null}
              {risk.caveats && risk.caveats.length > 0 ? (
                <div className="mt-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                    {t.riskCaveats}
                  </p>
                  <ul className="mt-1 list-disc space-y-1 ps-5 text-xs text-zinc-600 dark:text-zinc-400">
                    {risk.caveats.map((caveat) => (
                      <li key={caveat} dir="ltr" lang="en" className="text-start">
                        {caveat}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : (
            <>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">{t.riskNotMeasured}</p>
              <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{riskTargetLine}</p>
              {risk?.reason ? (
                <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                  {t.riskReason} <Ltr>{risk.reason}</Ltr>
                </p>
              ) : null}
              {risk?.error ? (
                <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                  {t.riskError} <Ltr>{risk.error}</Ltr>
                </p>
              ) : null}
            </>
          )}
        </div>
      </section>

      <section aria-label={t.runsTitle}>
        <h2 className="text-lg font-semibold tracking-tight">{t.runsTitle}</h2>
        <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label={t.total} value={runs.total} />
          <Stat label={t.completed} value={runs.completed} />
          <Stat label={t.failed} value={runs.failed} />
          <Stat label={t.p50} value={runs.p50_ms != null ? `${runs.p50_ms}ms` : DASH} />
          <Stat label={t.p95} value={runs.p95_ms != null ? `${runs.p95_ms}ms` : DASH} />
          <Stat label={t.p99} value={runs.p99_ms != null ? `${runs.p99_ms}ms` : DASH} />
        </dl>
        <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{t.runsHint}</p>
      </section>

      <section aria-label={t.optimizerTitle}>
        <h2 className="text-lg font-semibold tracking-tight">{t.optimizerTitle}</h2>
        {optimizerRuns.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{t.optimizerEmpty}</p>
        ) : (
          <div className="mt-3 rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="w-full overflow-x-auto">
              <table className="w-full min-w-[46rem] border-collapse text-sm">
                <thead>
                  <tr>
                    <th scope="col" className={`${TH} text-start`}>
                      {t.colStarted}
                    </th>
                    <th scope="col" className={`${TH} text-start`}>
                      {t.colOptimizer}
                    </th>
                    <th scope="col" className={`${TH} text-start`}>
                      {t.colAuto}
                    </th>
                    <th scope="col" className={`${TH} text-end`}>
                      {t.colTrainVal}
                    </th>
                    <th scope="col" className={`${TH} text-end`}>
                      {t.colBaseline}
                    </th>
                    <th scope="col" className={`${TH} text-end`}>
                      {t.colBest}
                    </th>
                    <th scope="col" className={`${TH} text-end`}>
                      {t.colTrialCount}
                    </th>
                    <th scope="col" className={`${TH} text-start`}>
                      {t.colArtifact}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {optimizerRuns.map((run) => (
                    <tr key={run.run_id}>
                      <td className={`${TD} whitespace-nowrap`}>
                        {formatDateTime(run.started_at, intl)}
                      </td>
                      <td className={`${TD}`}>
                        <Ltr className="font-mono text-xs">{run.optimizer}</Ltr>
                      </td>
                      <td className={`${TD}`}>
                        {run.auto ? <Ltr className="font-mono text-xs">{run.auto}</Ltr> : DASH}
                      </td>
                      <td className={`${TD} ${NUM} text-end whitespace-nowrap`}>
                        {run.trainset_size} / {run.valset_size}
                      </td>
                      <td className={`${TD} ${NUM} text-end`}>{num(run.baseline_score)}</td>
                      <td className={`${TD} ${NUM} text-end font-semibold`}>
                        {num(run.best_score)}
                      </td>
                      <td className={`${TD} ${NUM} text-end`}>{run.trial_count}</td>
                      <td className={`${TD}`}>
                        {run.artifact_sha ? (
                          <Ltr className="font-mono text-xs">
                            <span title={run.artifact_sha}>{run.artifact_sha.slice(0, 12)}</span>
                          </Ltr>
                        ) : (
                          DASH
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {trials.length > 0 ? (
              <div className="mt-5">
                <h3 className="text-sm font-semibold">{t.trialsTitle}</h3>
                <div className="mt-2 w-full overflow-x-auto">
                  <table className="w-full min-w-[34rem] border-collapse text-sm">
                    <thead>
                      <tr>
                        <th scope="col" className={`${TH} text-end`}>
                          {t.colTrial}
                        </th>
                        <th scope="col" className={`${TH} text-end`}>
                          {t.colScore}
                        </th>
                        <th scope="col" className={`${TH} text-start`}>
                          {t.colInstruction}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {trials.map((trial) => (
                        <tr key={trial.index}>
                          <td className={`${TD} ${NUM} text-end`}>{trial.index}</td>
                          <td className={`${TD} ${NUM} text-end`}>{num(trial.score)}</td>
                          <td className={`${TD}`}>
                            <span
                              dir="ltr"
                              lang="en"
                              title={trial.instruction_preview}
                              className="block max-w-[26rem] truncate text-start font-mono text-xs"
                            >
                              {trial.instruction_preview}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}

            {history?.path ? (
              <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
                {t.optimizerPath} <Ltr className="font-mono">{history.path}</Ltr>
              </p>
            ) : null}
          </div>
        )}
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
