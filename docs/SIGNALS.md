# MFA Platform — Signal Feature Schema

## Storage

- **Online:** Postgres JSONB column `signals` on `signal_snapshots` table, keyed by `url_id` + `version`
- **Offline:** Parquet in S3 data lake for training pipelines
- **Current:** 16 crawl-extractable features (`schema_version: v1`) — see below
- **Target:** ~40–60 features with enrichment and dual-persona (see [Roadmap](ROADMAP.md))

## Crawl features (`v1`)

Extracted by the crawler from DOM and content heuristics. Implemented in `backend/src/mfa/schemas/signals.py` as `SignalFeatures`.

| Feature | Type | Range | Null when |
|---------|------|-------|-----------|
| `ad_to_content_ratio` | float | 0–1 | Not measured |
| `ads_above_fold` | int | ≥0 | Not measured |
| `ad_slots_count` | int | ≥0 | Not measured |
| `sticky_ad_count` | int | ≥0 | Not measured |
| `content_word_count` | int | ≥0 | Not measured |
| `refresh_events_60s` | int | ≥0 | Dwell not run |
| `avg_refresh_interval_sec` | float | ≥0 | No refresh events |
| `content_uniqueness_score` | float | 0–1 | Heuristic unavailable |
| `author_page_exists` | bool | — | Not detected |
| `slideshow_pagination_depth` | int | ≥0 | Not a slideshow |
| `video_autoplay_count` | int | ≥0 | Not measured |
| `page_load_ad_latency_ms` | float | ≥0 | Not measured |
| `iframe_ad_count` | int | ≥0 | Not measured |
| `native_ad_count` | int | ≥0 | Not measured |
| `outbound_link_count` | int | ≥0 | Not measured |
| `image_to_text_ratio` | float | ≥0 | Not measured |

**JSONB envelope** (flat feature keys at top level after persistence):

```json
{
  "schema_version": "v1",
  "crawl_ts": "2026-07-06T12:00:00Z",
  "ad_to_content_ratio": 0.42,
  "ads_above_fold": 3,
  "content_word_count": 450
}
```

**Row-level columns** (also on `signal_snapshots` table): `persona` (`direct` | `referral`), `crawl_duration_sec`, `evidence_hash`.

### Null vs 0 conventions

| Situation | Store |
|-----------|--------|
| Signal not applicable (e.g. slideshow depth on article page) | `null` |
| Measured zero (e.g. no sticky ads) | `0` or `0.0` |
| Refresh not observed during dwell | `refresh_events_60s: null` (not `0`) until dwell is enabled |
| Enrichment unavailable (traffic %, domain age) | omit key or `null` — never `0` as placeholder |

## Enrichment features (planned)

Added with enrichment workers, dual-persona crawl, and 60s refresh dwell — tracked in `ENRICHMENT_FEATURE_NAMES` and [build plan](plans/2026-07-05-phased-build-plan.md) MVP tasks:

```
domain_age_days
paid_traffic_pct
social_traffic_pct
organic_traffic_pct
referral_direct_delta_score
sellers_json_risk_tier
historical_spend_usd
campaign_ctr_vs_benchmark
simhash_dup_rate
llm_content_quality_score
```

## Feature conventions

- All ratios in 0–1 unless documented otherwise
- Percentages stored as 0–100 floats with `_pct` suffix
- Counts are non-negative integers
- Missing enrichment signals → `null` (not 0) — ML pipeline handles imputation
- Every snapshot includes `crawl_ts` in JSONB; `persona` and `crawl_duration_sec` on the row

## Evidence artifacts

| Stage | Location |
|-------|----------|
| Local dev | `backend/evidence/{url_id}/{version}/` (screenshot, HTML, `dom_metrics.json`) |
| Deployed | S3 `s3://{bucket}/evidence/{url_id}/{version}/` |

Compute `evidence_hash` = SHA-256 of canonical JSON (`sort_keys=True`) of the `signals` document.

## SHAP / attribution

Store `top_signals` on classification: `[{name, value, contribution}]` — used by explanations and RAG.
