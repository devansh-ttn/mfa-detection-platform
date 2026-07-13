import type { TopSignalRow } from "../api/types";

type SignalBarChartProps = {
  signals: unknown[];
};

function normalizeSignals(signals: unknown[]): TopSignalRow[] {
  return signals.map((raw) => raw as TopSignalRow);
}

export function SignalBarChart({ signals }: SignalBarChartProps) {
  const rows = normalizeSignals(signals).filter(
    (row) => row.contribution != null && row.contribution > 0,
  );

  if (rows.length === 0) {
    return <p className="muted-text">No signal contributions available.</p>;
  }

  const maxContribution = Math.max(
    ...rows.map((row) => row.contribution ?? 0),
    0.01,
  );

  return (
    <div
      className="signal-chart"
      role="img"
      aria-label="Top signal contributions bar chart"
    >
      <ul className="signal-chart-list">
        {rows.map((row, index) => {
          const label = row.feature ?? row.name ?? `signal ${index + 1}`;
          const contribution = row.contribution ?? 0;
          const widthPct = Math.round((contribution / maxContribution) * 100);
          return (
            <li key={`${label}-${index}`} className="signal-chart-row">
              <span className="signal-chart-label" title={label}>
                {label}
              </span>
              <div className="signal-chart-bar-track" aria-hidden="true">
                <div
                  className="signal-chart-bar-fill"
                  style={{ width: `${widthPct}%` }}
                />
              </div>
              <span className="signal-chart-value">
                {contribution.toFixed(2)}
                {row.value != null && (
                  <span className="signal-chart-raw"> ({String(row.value)})</span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
