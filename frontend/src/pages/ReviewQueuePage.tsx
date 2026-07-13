import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { getReviewQueue } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import type { ReviewQueueItem } from "../api/types";
import { ForbiddenBanner } from "../components/ForbiddenBanner";
import { DetailPage } from "./DetailPage";

const TIER_FILTERS = ["MFA_Medium", "Uncertain"] as const;

function tierClass(tier: string): string {
  const normalized = tier.replace(/\s+/g, "_");
  return `tier-badge tier-${normalized}`;
}

type ReviewQueuePageProps = {
  onSelectOverride: (classificationId: string) => void;
  canOverride: boolean;
};

export function ReviewQueuePage({
  onSelectOverride,
  canOverride,
}: ReviewQueuePageProps) {
  const [tierFilter, setTierFilter] = useState<string[]>([...TIER_FILTERS]);
  const [domainFilter, setDomainFilter] = useState("");
  const [appliedTier, setAppliedTier] = useState<string[]>([...TIER_FILTERS]);
  const [appliedDomain, setAppliedDomain] = useState("");
  const [selected, setSelected] = useState<ReviewQueueItem | null>(null);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const rowRefs = useRef<(HTMLTableRowElement | null)[]>([]);

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: queryKeys.reviewQueue(appliedTier, appliedDomain),
    queryFn: () =>
      getReviewQueue({
        tier: appliedTier.length ? appliedTier : undefined,
        domain: appliedDomain.trim() || undefined,
      }),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const openDetail = useCallback((item: ReviewQueueItem) => {
    setSelected(item);
  }, []);

  useEffect(() => {
    setFocusedIndex(0);
    rowRefs.current = [];
  }, [items]);

  useEffect(() => {
    const row = rowRefs.current[focusedIndex];
    row?.focus();
  }, [focusedIndex, items]);

  function applyFilters() {
    setAppliedTier([...tierFilter]);
    setAppliedDomain(domainFilter);
  }

  function handleTableKeyDown(event: KeyboardEvent<HTMLTableSectionElement>) {
    if (items.length === 0) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setFocusedIndex((i) => Math.min(i + 1, items.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setFocusedIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === "Home") {
      event.preventDefault();
      setFocusedIndex(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setFocusedIndex(items.length - 1);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const item = items[focusedIndex];
      if (item) openDetail(item);
    }
  }

  if (selected) {
    return (
      <DetailPage
        item={selected}
        onBack={() => setSelected(null)}
        onOverride={
          canOverride
            ? (id) => {
                setSelected(null);
                onSelectOverride(id);
              }
            : undefined
        }
      />
    );
  }

  return (
    <section aria-labelledby="review-queue-title">
      <h2 id="review-queue-title" className="page-title">
        Review Queue
      </h2>
      <div className="card" style={{ marginBottom: "1rem" }}>
        <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr auto" }}>
          <label htmlFor="tier-filter">
            Tier
            <select
              id="tier-filter"
              multiple
              value={tierFilter}
              onChange={(e) =>
                setTierFilter(
                  Array.from(e.target.selectedOptions, (o) => o.value),
                )
              }
              size={2}
            >
              {TIER_FILTERS.map((tier) => (
                <option key={tier} value={tier}>
                  {tier}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="domain-filter">
            Domain
            <input
              id="domain-filter"
              type="text"
              value={domainFilter}
              onChange={(e) => setDomainFilter(e.target.value)}
              placeholder="filter by domain"
            />
          </label>
          <button type="button" onClick={applyFilters} disabled={isFetching}>
            Apply
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="status loading" aria-live="polite">
          Loading queue…
        </div>
      )}

      {error && <ForbiddenBanner error={error} fallback="Failed to load review queue" />}

      {!isLoading && !error && (
        <div className="card">
          {items.length === 0 ? (
            <p>No items in the review queue.</p>
          ) : (
            <>
              <p className="muted-text queue-kbd-hint" id="queue-kbd-hint">
                Keyboard: ↑↓ move row, Enter open detail, Home/End jump.
              </p>
              <table aria-label="Review queue" aria-describedby="queue-kbd-hint">
                <thead>
                  <tr>
                    <th scope="col">Domain</th>
                    <th scope="col">Tier</th>
                    <th scope="col">Score</th>
                    <th scope="col">Confidence</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody onKeyDown={handleTableKeyDown}>
                  {items.map((item, index) => (
                    <tr
                      key={item.classification_id}
                      ref={(el) => {
                        rowRefs.current[index] = el;
                      }}
                      tabIndex={index === focusedIndex ? 0 : -1}
                      className={index === focusedIndex ? "row-focused" : undefined}
                      aria-selected={index === focusedIndex}
                      onClick={() => {
                        setFocusedIndex(index);
                        openDetail(item);
                      }}
                      onFocus={() => setFocusedIndex(index)}
                    >
                      <td>{item.domain}</td>
                      <td>
                        <span className={tierClass(item.tier)}>{item.tier}</span>
                      </td>
                      <td>{item.mfa_score.toFixed(3)}</td>
                      <td>{item.confidence}</td>
                      <td>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            openDetail(item);
                          }}
                        >
                          Detail
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="table-footer">
                Showing {items.length} of {total} items
                {isFetching && !isLoading ? " · refreshing…" : ""}
              </p>
              <button
                type="button"
                className="link-button"
                onClick={() => void refetch()}
                disabled={isFetching}
              >
                Refresh
              </button>
            </>
          )}
        </div>
      )}
    </section>
  );
}
