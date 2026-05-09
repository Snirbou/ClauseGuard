export type ParsedClause = {
  parsed_clause_id: string;
  contract_id: string;
  clause_index: number;
  raw_text: string;
  clause_type: string;
  clause_type_confidence: number;
};

export type UploadSuccessResponse = {
  status: "success";
  filename: string;
  contract_id: string;
  parsed_clauses: ParsedClause[];
};

export type UploadErrorResponse = {
  status: "error";
  filename: string;
  contract_id: string | null;
  parsed_clauses: ParsedClause[];
  detail?: string;
};

export type UploadResponse = UploadSuccessResponse | UploadErrorResponse;

export type RiskLevel = "low" | "medium" | "high";

export type ClauseResult = ParsedClause & {
  plain_language_summary: string | null;
  risk_factors: string[] | null;
  dspy_risk_score: number | null;
  risk_level: RiskLevel | null;
};

export type ContractResultsSuccess = {
  status: "success";
  contract_id: string;
  filename: string;
  clauses: ClauseResult[];
  disclaimer: string;
  detail?: string;
};

export type ContractResultsError = {
  status: "error";
  contract_id: string;
  filename: string;
  clauses: [];
  disclaimer: string;
  detail: string;
};

export type ContractResultsResponse = ContractResultsSuccess | ContractResultsError;

/** Saved contracts row for dashboard list (GET /api/contracts). */
export type UserContractSummary = {
  contract_id: string;
  filename: string;
  created_at: string;
  clause_count: number;
};
