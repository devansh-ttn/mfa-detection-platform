import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getBlocklist } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { ForbiddenBanner } from "../components/ForbiddenBanner";

const DEFAULT_TIERS = ["MFA_High"] as const;

function tierClass(tier: string): string {
  const normalized = tier.replace(/\s+/g, "_");
  return `tier-badge tier-${normalized}`;
}

export function BlocklistPage() {
  const [tierFilter, setTierFilter] = useState<string[]>([...DEFAULT_TIERS]);
  const [domainFilter, setDomainFilter] = useState("");
  const [appliedTier, setAppliedTier] = useState<string[]>([...DEFAULT_TIERS]);
  const [appliedDomain, setAppliedDomain] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: queryKeys.blocklist(appliedTier, appliedDomain, offset),
    queryFn: () =>
      getBlocklist({
        tier: appliedTier.length ? appliedTier : undefined,
        domain: appliedDomain.trim() || undefined,
        limit,
        offset,
      }),
  });

  const entries = data?.entries ?? [];
  const total = data?.total ?? 0;

  function applyFilters() {
    setAppliedTier([...tierFilter]);
    setAppliedDomain(domainFilter);
    setOffset(0);
  }

  return (
    <section>
      <h2 className="page-title">Blocklist export</h2>
      <p className="muted-text" style={{ marginTop: "-0.5rem" }}>
        Latest classifications for block tiers (default MFA_High).
      </p>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr auto" }}>
          <label htmlFor="blocklist-tier">
            Tier
            <select
              id="blocklist-tier"
              multiple
              value={tierFilter}
              onChange={(e) =>
                setTierFilter(
                  Array.from(e.target.selectedOptions, (o) => o.value),
                )
              }
              size={3}
            >
              {["MFA_High", "MFA_Medium", "MFA_Low"].map((tier) => (
                <option key={tier} value={tier}>
                  {tier}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="blocklist-domain">
            Domain
            <input
              id="blocklist-domain"
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
          Loading blocklist…
        </div>
      )}

      {error && (
        <ForbiddenBanner error={error} fallback="Failed to load blocklist" />
      )}

      {!isLoading && !error && (
        <div className="card">
          {entries.length === 0 ? (
            <p>No blocklist entries match the current filters.</p>
          ) : (
            <>
              <table aria-label="Blocklist entries">
                <thead>
                  <tr>
                    <th scope="col">Domain</th>
                    <th scope="col">Tier</th>
                    <th scope="col">Score</th>
                    <th scope="col">Confidence</th>
                    <th scope="col">URL</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={`${entry.domain}-${entry.evidence_hash}`}>
                      <td>{entry.domain}</td>
                      <td>
                        <span className={tierClass(entry.tier)}>{entry.tier}</span>
                      </td>
                      <td>{entry.mfa_score.toFixed(3)}</td>
                      <td>{entry.confidence}</td>
                      <td className="url-cell">{entry.url}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="table-footer pagination-row">
                <span>
                  Showing {offset + 1}–{offset + entries.length} of {total}
                </span>
                <div className="pagination-buttons">
                  <button
                    type="button"
                    disabled={offset === 0 || isFetching}
                    onClick={() => setOffset((o) => Math.max(0, o - limit))}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    disabled={offset + entries.length >= total || isFetching}
                    onClick={() => setOffset((o) => o + limit)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
