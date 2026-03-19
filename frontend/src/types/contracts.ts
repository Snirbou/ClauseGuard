export type ParsedClause = {
  clause_index: number;
  raw_text: string;
};

export type UploadSuccessResponse = {
  status: "success";
  filename: string;
  parsed_clauses: ParsedClause[];
};

export type UploadErrorResponse = {
  status: "error";
  filename: string;
  parsed_clauses: ParsedClause[];
  detail?: string;
};

export type UploadResponse = UploadSuccessResponse | UploadErrorResponse;

