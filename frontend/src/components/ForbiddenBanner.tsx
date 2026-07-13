import { ApiClientError } from "../api/client";

/** Human-readable message for API failures, with emphasis on 403. */
export function formatApiError(err: unknown, fallback = "Request failed"): string {
  if (!(err instanceof ApiClientError)) {
    return fallback;
  }
  if (err.status === 403) {
    return `Forbidden (403): ${err.message}. Your role may not have permission for this action.`;
  }
  if (err.status === 401) {
    return `Unauthorized (401): ${err.message}. Sign in again or choose a role with access.`;
  }
  return err.message;
}

interface ForbiddenBannerProps {
  error: unknown;
  fallback?: string;
}

export function ForbiddenBanner({ error, fallback }: ForbiddenBannerProps) {
  if (!error) return null;
  const message = formatApiError(error, fallback);
  const isForbidden = error instanceof ApiClientError && error.status === 403;

  return (
    <div
      className={`status error${isForbidden ? " status-forbidden" : ""}`}
      role="alert"
    >
      {message}
    </div>
  );
}
