# MFA Platform — Signal Feature Schema

## Storage

- **Online:** Postgres JSONB column `signals` on `signal_snapshots` table, keyed by `url_id` + `version`
- **Offline:** Parquet in S3 data lake for training pipelines
- **Target:** ~40–60 features for MVP

## Core features (MVP subset)

```
domain_age_days
ad_to_content_ratio
ads_above_fold
ad_slots_count
refresh_events_60s
avg_refresh_interval_sec
paid_traffic_pct
social_traffic_pct
organic_traffic_pct
referral_direct_delta_score
content_word_count
content_uniqueness_score
author_page_exists
slideshow_pagination_depth
video_autoplay_count
sticky_ad_count
page_load_ad_latency_ms
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
- Every snapshot includes `crawl_ts`, `persona` (`direct` | `referral`), `crawl_duration_sec`

## Evidence artifacts (S3)

| Artifact | Path pattern |
|----------|--------------|
| Screenshot | `s3://{bucket}/evidence/{url_id}/{version}/screenshot.png` |
| HTML | `s3://{bucket}/evidence/{url_id}/{version}/page.html` |
| DOM metrics | `s3://{bucket}/evidence/{url_id}/{version}/dom_metrics.json` |

## SHAP / attribution

Store `top_signals` on classification: `[{name, value, contribution}]` — used by explanations and RAG.
