import type {
  ApiError,
  AuditEventListResponse,
  BlocklistResponse,
  ChatRequest,
  EvidenceArtifactListResponse,
  RAGResponse,
  ReviewOverrideRequest,
  ReviewOverrideResponse,
  ReviewQueueItem,
  ReviewQueueResponse,
} from "./types";

/** Base URL for API calls. Empty string uses same-origin `/api` (Vite dev proxy). */
export const API_BASE = import.meta.env.VITE_API_URL ?? "";

let authHeaderProvider: (() => Record<string, string>) | null = null;

/** Called by AuthProvider to inject Authorization Bearer or dev headers. */
export function setAuthHeaderProvider(
  provider: () => Record<string, string>,
): void {
  authHeaderProvider = provider;
}

function getAuthHeaders(): Record<string, string> {
  return authHeaderProvider?.() ?? {};
}

class ApiClientError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
  }
}

function parseErrorBody(body: unknown): { message: string; code?: string } {
  if (typeof body !== "object" || body === null) {
    return { message: "Request failed" };
  }

  const record = body as Record<string, unknown>;

  if (typeof record.error === "string") {
    return {
      message: record.error,
      code: typeof record.code === "string" ? record.code : undefined,
    };
  }

  const detail = record.detail;
  if (typeof detail === "string") {
    return { message: detail };
  }
  if (typeof detail === "object" && detail !== null) {
    const nested = detail as Record<string, unknown>;
    if (typeof nested.error === "string") {
      return {
        message: nested.error,
        code: typeof nested.code === "string" ? nested.code : undefined,
      };
    }
  }

  return { message: "Request failed" };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    let code: string | undefined;
    try {
      const body = await response.json();
      const parsed = parseErrorBody(body as ApiError);
      message = parsed.message;
      code = parsed.code;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiClientError(message, response.status, code);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function getReviewQueue(params?: {
  tier?: string[];
  domain?: string;
  limit?: number;
  offset?: number;
}): Promise<ReviewQueueResponse> {
  const search = new URLSearchParams();
  params?.tier?.forEach((t) => search.append("tier", t));
  if (params?.domain) search.set("domain", params.domain);
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.offset != null) search.set("offset", String(params.offset));

  const qs = search.toString();
  return request<ReviewQueueResponse>(
    `/api/v1/reviews/queue${qs ? `?${qs}` : ""}`,
  );
}

export async function submitReviewOverride(
  body: ReviewOverrideRequest,
): Promise<ReviewOverrideResponse> {
  return request<ReviewOverrideResponse>("/api/v1/reviews", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function postChat(body: ChatRequest): Promise<RAGResponse> {
  return request<RAGResponse>("/api/v1/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getAuditEvents(
  urlId: string,
  params?: { limit?: number; offset?: number },
): Promise<AuditEventListResponse> {
  const search = new URLSearchParams({ url_id: urlId });
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.offset != null) search.set("offset", String(params.offset));
  return request<AuditEventListResponse>(`/api/v1/audit?${search.toString()}`);
}

export async function getEvidenceArtifacts(
  urlId: string,
): Promise<EvidenceArtifactListResponse> {
  return request<EvidenceArtifactListResponse>(
    `/api/v1/urls/${urlId}/evidence`,
  );
}

/** Resolve evidence proxy URL (same-origin when API_BASE is empty). */
export function evidenceAssetUrl(path: string): string {
  return `${API_BASE}${path}`;
}

/** Fetch evidence bytes with auth headers (for img tags that cannot send headers). */
export async function fetchEvidenceBlob(path: string): Promise<Blob> {
  const response = await fetch(evidenceAssetUrl(path), {
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    throw new ApiClientError(
      `Evidence fetch failed (${response.status})`,
      response.status,
    );
  }
  return response.blob();
}

export async function getBlocklist(params?: {
  tier?: string[];
  domain?: string;
  limit?: number;
  offset?: number;
}): Promise<BlocklistResponse> {
  const search = new URLSearchParams();
  params?.tier?.forEach((t) => search.append("tier", t));
  if (params?.domain) search.set("domain", params.domain);
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.offset != null) search.set("offset", String(params.offset));
  const qs = search.toString();
  return request<BlocklistResponse>(
    `/api/v1/blocklist${qs ? `?${qs}` : ""}`,
  );
}

export type { ReviewQueueItem };
export { ApiClientError };
