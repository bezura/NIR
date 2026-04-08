export type SourceType = "note" | "snippet" | "web_page" | "article" | "document";
export type TaggingMode = "generate" | "existing_only" | "curated_only" | "hybrid";
export type OutputLanguage = "auto" | "ru" | "en";
export type LlmStrategy = "disabled" | "low_confidence_only" | "always";
export type TagSource = "manual" | "rule" | "model" | "llm";
export type JobStageStatus = "pending" | "in_progress" | "completed" | "skipped" | "failed";

export interface TagCatalogEntry {
  canonical_name: string;
  aliases: string[];
  labels: Record<string, string>;
  category_codes: string[];
}

export interface TaggingOptions {
  max_tags: number;
  use_llm_postprocess: boolean;
  tagging_mode: TaggingMode;
  output_language: OutputLanguage;
  enable_rules: boolean;
  llm_strategy: LlmStrategy;
  existing_tags?: TagCatalogEntry[];
  curated_tags?: TagCatalogEntry[];
  content_type_hint?: string | null;
}

export interface CreateJobPayload {
  text: string;
  source: SourceType;
  metadata: Record<string, unknown>;
  options: TaggingOptions;
}

export interface CreateJobResponse {
  job_id: string;
  status: string;
  document_id: string;
  status_url: string;
  result_url: string;
}

export interface ErrorPayload {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface JobStageResponse {
  name: string;
  label: string;
  status: JobStageStatus;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface JobStatusResponse {
  job_id: string;
  document_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  result_available: boolean;
  current_stage?: string | null;
  stage_label?: string | null;
  progress_percent: number;
  stage_history: JobStageResponse[];
  pending_stages: JobStageResponse[];
  error?: ErrorPayload | null;
}

export interface CategoryResponse {
  code: string;
  label: string;
  score: number;
}

export interface TagResponse {
  label: string;
  normalized_label: string;
  score: number;
  source: TagSource;
  method: string;
  confidence?: number | null;
  reason?: string | null;
  canonical_name?: string | null;
}

export interface JobResultResponse {
  job_id: string;
  document_id: string;
  category: CategoryResponse;
  tags: TagResponse[];
  score: number;
  signals: Record<string, unknown>;
  explanation?: string | null;
}

export interface RequestDraft {
  apiBaseUrl: string;
  text: string;
  source: SourceType;
  title: string;
  language: string;
  collection: string;
  keywords: string;
  author: string;
  maxTags: number;
  useLlmPostprocess: boolean;
  taggingMode: TaggingMode;
  outputLanguage: OutputLanguage;
  enableRules: boolean;
  llmStrategy: LlmStrategy;
}

export type RequestCardPhase = "queued" | "processing" | "completed" | "failed";

export interface RequestCard {
  localId: string;
  createdAt: number;
  phase: RequestCardPhase;
  payload: CreateJobPayload;
  title: string;
  preview: string;
  jobId?: string;
  documentId?: string;
  status?: JobStatusResponse;
  result?: JobResultResponse;
  error?: ErrorPayload | { code: string; message: string };
}
