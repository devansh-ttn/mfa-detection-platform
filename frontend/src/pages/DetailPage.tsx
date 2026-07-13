import { AuditSidebar } from "../components/AuditSidebar";
import { EvidenceThumbnails } from "../components/EvidenceThumbnails";
import { SignalBarChart } from "../components/SignalBarChart";
import type { ReviewQueueItem } from "../api/types";

type DetailPageProps = {
  item: ReviewQueueItem;
  onBack: () => void;
  onOverride?: (classificationId: string) => void;
};

function tierClass(tier: string): string {
  const normalized = tier.replace(/\s+/g, "_");
  return `tier-badge tier-${normalized}`;
}

export function DetailPage({ item, onBack, onOverride }: DetailPageProps) {
  return (
    <section>
      <button type="button" className="link-button" onClick={onBack}>
        ← Back to queue
      </button>
      <h2 className="page-title">Review detail — {item.domain}</h2>

      <div className="detail-layout">
        <div className="detail-main card">
          <div className="meta-row">
            <span className={tierClass(item.tier)}>{item.tier}</span>
            <span className="meta-pill">
              Score: <strong>{item.mfa_score.toFixed(3)}</strong>
            </span>
            <span className="meta-pill">
              Confidence: <strong>{item.confidence}</strong>
            </span>
          </div>

          <p className="muted-text">URL: {item.url}</p>

          <h3 className="section-heading">Explanation</h3>
          <p className="answer-text">{item.explanation}</p>

          {item.top_signals.length > 0 && (
            <>
              <h3 className="section-heading">Top signals</h3>
              <SignalBarChart signals={item.top_signals} />
            </>
          )}

          <h3 className="section-heading">Evidence</h3>
          <EvidenceThumbnails urlId={item.url_id} />

          <p className="evidence-hash-line">
            Evidence hash: <code>{item.evidence_hash.slice(0, 16)}…</code>
          </p>

          {onOverride && (
            <button
              type="button"
              className="btn-primary"
              style={{ marginTop: "1rem" }}
              onClick={() => onOverride(item.classification_id)}
            >
              Submit override
            </button>
          )}
        </div>

        <AuditSidebar urlId={item.url_id} />
      </div>
    </section>
  );
}
