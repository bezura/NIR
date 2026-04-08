import type {
  CreateJobPayload,
  CreateJobResponse,
  JobResultResponse,
  JobStatusResponse,
} from "../types/tagging";
import { normalizeApiBaseUrl } from "./job-state";

export class ApiClientError extends Error {
  status: number;
  code: string;
  details?: Record<string, unknown> | null;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown> | null) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const LOCAL_BACKEND_ORIGINS = new Set(["http://127.0.0.1:8000", "http://localhost:8000"]);

function isViteLocalOrigin(currentOrigin?: string) {
  if (!currentOrigin) {
    return false;
  }

  try {
    const parsed = new URL(currentOrigin);
    return ["5173", "4173"].includes(parsed.port);
  } catch {
    return false;
  }
}

export function resolveApiBaseUrl(apiBaseUrl: string, currentOrigin?: string) {
  const normalized = normalizeApiBaseUrl(apiBaseUrl);
  if (!normalized) {
    return normalized;
  }

  try {
    const parsed = new URL(normalized);
    if (isViteLocalOrigin(currentOrigin) && LOCAL_BACKEND_ORIGINS.has(parsed.origin)) {
      return parsed.pathname;
    }

    return parsed.toString().replace(/\/+$/, "");
  } catch {
    return normalized;
  }
}

function buildApiUrl(apiBaseUrl: string, path: string, currentOrigin?: string) {
  return `${resolveApiBaseUrl(apiBaseUrl, currentOrigin)}${path}`;
}

export function buildReadinessUrl(apiBaseUrl: string, currentOrigin?: string) {
  const resolved = resolveApiBaseUrl(apiBaseUrl, currentOrigin);
  if (!resolved) {
    return "/readiness";
  }

  if (resolved.startsWith("/")) {
    return "/readiness";
  }

  const parsed = new URL(resolved);
  parsed.pathname = "/readiness";
  return parsed.toString();
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const body = isJson ? ((await response.json()) as Record<string, unknown>) : null;

  if (!response.ok) {
    const errorPayload = body && "error" in body ? (body.error as Record<string, unknown>) : null;
    throw new ApiClientError(
      response.status,
      typeof errorPayload?.code === "string" ? errorPayload.code : "request_failed",
      typeof errorPayload?.message === "string" ? errorPayload.message : `Request failed with ${response.status}`,
      (errorPayload?.details as Record<string, unknown> | null | undefined) ?? null,
    );
  }

  return body as T;
}

export function isApiClientError(error: unknown): error is ApiClientError {
  return error instanceof ApiClientError;
}

export async function pingReadiness(apiBaseUrl: string) {
  return requestJson<{ status: string; service: string }>(
    buildReadinessUrl(apiBaseUrl, typeof window !== "undefined" ? window.location.origin : undefined),
  );
}

export async function createJob(apiBaseUrl: string, payload: CreateJobPayload) {
  return requestJson<CreateJobResponse>(
    buildApiUrl(apiBaseUrl, "/jobs", typeof window !== "undefined" ? window.location.origin : undefined),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
}

export async function getJobStatus(apiBaseUrl: string, jobId: string) {
  return requestJson<JobStatusResponse>(
    buildApiUrl(
      apiBaseUrl,
      `/jobs/${jobId}`,
      typeof window !== "undefined" ? window.location.origin : undefined,
    ),
  );
}

export async function getJobResult(apiBaseUrl: string, jobId: string) {
  return requestJson<JobResultResponse>(
    buildApiUrl(
      apiBaseUrl,
      `/jobs/${jobId}/result`,
      typeof window !== "undefined" ? window.location.origin : undefined,
    ),
  );
}
