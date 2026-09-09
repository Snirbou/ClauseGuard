/**
 * Wire types for the ClauseGuard API.
 *
 * These mirror `backend/api_schemas.py` and the upload endpoint in
 * `backend/main.py`. Keep them in sync when the API changes.
 */

export type RiskLevel = "high" | "medium" | "low";

/** Maximum upload size accepted by the backend (`MAX_UPLOAD_BYTES`). */
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

/** A clause as returned by POST /api/contracts/upload. */
export type ParsedClause = {
  parsed_clause_id: string;
  contract_id: string;
  clause_index: number;
  raw_text: string;
  clause_type: string | null;
  clause_type_confidence: number | null;
};

/** Present on upload responses only when AUTO_ANALYZE_ON_UPLOAD is enabled. */
export type UploadAnalysisInfo =
  | { status: "started"; run_id: string }
  | { status: "skipped"; detail: string; code?: string };

export type UploadSuccessResponse = {
  status: "success";
  filename: string;
  contract_id: string;
  parsed_clauses: ParsedClause[];
  analysis?: UploadAnalysisInfo;
};

export type UploadErrorResponse = {
  status: "error";
  filename: string;
  contract_id: string | null;
  parsed_clauses: ParsedClause[];
  detail?: string;
  /** Stable error code (backend/error_codes.py) for localized messages. */
  code?: string;
};

export type UploadResponse = UploadSuccessResponse | UploadErrorResponse;

/** Clause counts bucketed by risk level. Buckets sum to the clause count. */
export type RiskDistribution = {
  high: number;
  medium: number;
  low: number;
  unanalyzed: number;
};

/**
 * A parsed clause joined with its risk score.
 * Every risk field is null until the clause has been through the AI pipeline.
 */
export type ClauseDetail = ParsedClause & {
  risk_level: RiskLevel | null;
  risk_score: number | null;
  risk_percentile: number | null;
  risk_factors: string[];
  plain_language_summary: string | null;
  dspy_program_version: string | null;
  analyzed_at: string | null;
};

export type ContractSummary = {
  id: string;
  original_filename: string;
  created_at: string;
  clause_count: number;
  analyzed_clause_count: number;
  has_analysis: boolean;
};

export type ContractListResponse = {
  status: "success";
  count: number;
  contracts: ContractSummary[];
};

/** A contract-level finding — currently missing-protection detections. */
export type ContractFinding = {
  id: string;
  finding_type: "missing_protection" | string;
  pain_point: string;
  severity: "high" | "medium" | string;
  title: string;
  detail: string;
};

export type ContractDetail = {
  status: "success";
  id: string;
  original_filename: string;
  created_at: string;
  clause_count: number;
  analyzed_clause_count: number;
  has_analysis: boolean;
  risk_distribution: RiskDistribution;
  /** Contract-level executive summary from the latest analysis run. */
  analysis_summary: string | null;
  /** Missing-protection findings from the latest analysis run. */
  findings: ContractFinding[];
  /** Most recent analysis run — lets the UI resume polling after a refresh. */
  latest_run: AnalysisRun | null;
  clauses: ClauseDetail[];
};

export type AnalysisRunStatus = "pending" | "running" | "completed" | "failed";

/** One execution of the analysis pipeline. The shape the UI polls. */
export type AnalysisRun = {
  id: string;
  contract_id: string;
  status: AnalysisRunStatus;
  started_at: string;
  completed_at: string | null;
  processing_time_ms: number | null;
  clause_count: number | null;
  completed_clauses: number;
  error_message: string | null;
  run_metadata: {
    provider?: string;
    model?: string;
    dspy_version?: string;
    cached_clauses?: number;
    analyzed_clauses?: number;
    failed_parsed_clause_ids?: string[];
  } | null;
};

/** 202 body from POST /api/contracts/{id}/analyze. */
export type AnalyzeAcceptedResponse = {
  status: "accepted";
  run: AnalysisRun;
};

export type AnalysisRunResponse = {
  status: "success";
  run: AnalysisRun;
};

export type DeleteResponse = {
  status: "success";
  contract_id: string;
  deleted: boolean;
};

export type HealthResponse = {
  status: string;
  database: string;
  llm_configured: boolean;
  provider: string;
  model: string;
  auto_analyze_on_upload: boolean;
  max_upload_mb: number;
  /** Non-null when startup could not initialise the database (HTTP 503). */
  startup_error?: string | null;
};

/** One class's scores in the held-out evaluation report. */
type EvalClassMetrics = {
  precision: number;
  recall: number;
  f1: number;
  support: number;
};

/** One recorded DSPy optimizer run (`optimizer_history.runs[]`). */
type OptimizerRun = {
  run_id: string;
  started_at: string;
  finished_at: string;
  optimizer: string;
  /** MIPROv2 `auto` preset ("light" | "medium" | "heavy"), null for others. */
  auto: string | null;
  metric: string;
  trainset_size: number;
  valset_size: number;
  baseline_score: number | null;
  best_score: number | null;
  artifact_sha: string | null;
  trial_count: number;
};

/** One candidate the optimizer scored during its search. */
type OptimizerTrial = {
  index: number;
  score: number | null;
  instruction_preview: string;
};

/**
 * Payload of GET /api/metrics — the evaluation dashboard.
 *
 * Everything beyond the four original blocks is additive and optional: the
 * dashboard renders each section from whatever the server sends and falls
 * back to a placeholder when a block is missing.
 */
export type MetricsResponse = {
  status: "success";
  classifier: {
    mode: "model" | "mock" | string;
    low_confidence_threshold: number;
    load_error?: string;
    artifact?: string;
    trained_at_utc?: string;
    /** Training-time holdout macro F1 baked into the artifact. */
    test_macro_f1?: number;
    per_class_f1?: Record<string, number>;
    labels?: string[];
    sklearn_version_trained?: string;
    /** spaCy pipeline asked for by SPACY_MODEL vs the one actually loaded. */
    spacy_model_configured?: string;
    spacy_model_runtime?: string;
    spacy_model_version_runtime?: string;
    /** spaCy pipeline the artifact was trained against. */
    spacy_model_trained?: string;
    spacy_model_version_trained?: string;
    /** Held-out evaluation report (AC §4): per-class P/R/F1 + confusion matrix. */
    eval?: {
      dataset: string;
      split: string;
      n: number;
      spacy_model: string;
      spacy_model_version: string;
      labels: string[];
      macro_f1: number;
      /** Macro F1 of the served pipeline, including the confidence gate. */
      served_macro_f1: number;
      low_confidence_threshold: number;
      per_class: Record<string, EvalClassMetrics>;
      /** Rows are the true label, columns the predicted one, in `labels` order. */
      confusion_matrix: number[][];
      confusion_matrix_orientation: string;
      generated_at: string;
      note?: string;
    };
  };
  runs: {
    total: number;
    completed: number;
    failed: number;
    active: number;
    p50_ms: number | null;
    p95_ms: number | null;
    p99_ms?: number | null;
  };
  /** AC-P04: Flesch-Kincaid grade of the summaries actually served. */
  quality?: {
    readability?: {
      sample_size: number;
      avg_grade: number | null;
      median_grade: number | null;
      share_at_or_below_target: number | null;
      target_grade: number;
    };
  };
  /** AC-R05: high-risk precision/recall against labeled data. */
  risk?: {
    measured: boolean;
    targets: { precision: number; recall: number };
    /** Why the evaluation did not run (e.g. no LLM key configured). */
    reason?: string;
    error?: string;
    precision_high?: number;
    recall_high?: number;
    f1_high?: number;
    n?: number;
    threshold_high?: number;
    confusion?: Record<string, number>;
    dataset?: Record<string, number>;
    provider?: string;
    model?: string;
    caveats?: string[];
    generated_at?: string;
  };
  pipeline: {
    provider: string;
    model: string;
    concurrency: number;
    max_retries: number;
    /** Identity of the DSPy program actually serving requests. */
    dspy_program?: {
      optimized: boolean;
      artifact_sha: string | null;
      dspy_version: string;
      pipeline_version: string;
      fingerprint: string;
    };
    optimizer_history?: {
      path: string;
      runs: OptimizerRun[];
      latest: (OptimizerRun & { trials: OptimizerTrial[] }) | null;
    };
  };
  compliance: {
    disclaimer_views_logged: number;
  };
};

/** The signed-in user, as returned by the auth endpoints. */
export type UserInfo = {
  status: "success";
  id: string;
  email: string;
};

/** Error envelope returned by every non-upload endpoint. */
export type ApiErrorResponse = {
  status: "error";
  detail?: string;
  /** Stable error code (backend/error_codes.py) for localized messages. */
  code?: string;
};
