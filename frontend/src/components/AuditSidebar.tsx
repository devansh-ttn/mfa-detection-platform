import { useQuery } from "@tanstack/react-query";
import { getAuditEvents } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { ForbiddenBanner } from "./ForbiddenBanner";

type AuditSidebarProps = {
  urlId: string;
};

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function AuditSidebar({ urlId }: AuditSidebarProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.auditEvents(urlId),
    queryFn: () => getAuditEvents(urlId, { limit: 30 }),
  });

  return (
    <aside className="audit-sidebar" aria-label="Audit trail">
      <h3 className="sidebar-title">Audit trail</h3>

      {isLoading && (
        <p className="muted-text" aria-live="polite">
          Loading audit events…
        </p>
      )}

      {error && (
        <ForbiddenBanner error={error} fallback="Failed to load audit trail" />
      )}

      {!isLoading && !error && data?.items.length === 0 && (
        <p className="muted-text">No audit events for this URL yet.</p>
      )}

      {data && data.items.length > 0 && (
        <ol className="audit-list">
          {data.items.map((event) => (
            <li key={event.event_id} className="audit-item">
              <div className="audit-action">{event.action}</div>
              <div className="audit-meta">
                <span>{formatTimestamp(event.occurred_at)}</span>
                <span> · {event.actor_id}</span>
              </div>
              {event.evidence_hash && (
                <div className="audit-hash">
                  hash <code>{event.evidence_hash.slice(0, 12)}…</code>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}
