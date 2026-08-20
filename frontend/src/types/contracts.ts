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
  | { status: "skipped"; detail: string };

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
};

/** Payload of GET /api/metrics — the evaluation dashboard. */
export type MetricsResponse = {
  status: "success";
  classifier: {
    mode: "model" | "mock" | string;
    low_confidence_threshold: number;
    load_error?: string;
    artifact?: string;
    trained_at_utc?: string;
    test_macro_f1?: number;
    per_class_f1?: Record<string, number>;
    labels?: string[];
    sklearn_version_trained?: string;
  };
  runs: {
    total: number;
    completed: number;
    failed: number;
    active: number;
    p50_ms: number | null;
    p95_ms: number | null;
  };
  pipeline: {
    provider: string;
    model: string;
    concurrency: number;
    max_retries: number;
  };
  compliance: {
    disclaimer_views_logged: number;
  };
};

/** Error envelope returned by every non-upload endpoint. */
export type ApiErrorResponse = {
  status: "error";
  detail?: string;
};
