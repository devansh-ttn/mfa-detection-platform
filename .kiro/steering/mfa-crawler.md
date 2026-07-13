---
inclusion: fileMatch
fileMatchPattern: ['crawler/**/*', 'backend/**/crawler/**/*']
---

# MFA Platform — Crawler rules

Reference: **`docs/SIGNALS.md`**, **`docs/ADRS.md`** (ADR-003)

## Dual-persona

1. **Direct:** navigate URL without referrer
2. **Referral:** simulate Outbrain/Taboola referrer header

Compute `referral_direct_delta_score` from persona diffs.

> **TODO(MVP):** Dual-persona crawl — start with `direct` only; see `docs/ROADMAP.md`.

## Dwell & refresh

- Target **60s dwell** for refresh detection (`refresh_events_60s`, `avg_refresh_interval_sec`)
- Until dwell is wired, store `null` for refresh fields per `docs/SIGNALS.md`

## Page depth

- Deep-link into article paths — never score homepage-only
- Respect `robots.txt` (configurable); identify user-agent; rate limit per domain

## Evidence artifacts

Persist to S3 per `url_id` + `version`: screenshot, HTML, `dom_metrics.json`

## DOM metrics

Extract into `SignalFeatures` (`docs/SIGNALS.md`): `ad_to_content_ratio`, `ads_above_fold`, `ad_slots_count`, `sticky_ad_count`, `video_autoplay_count`

## Worker pattern

Crawler runs on ECS Fargate / worker pool via SQS — not inline in API handlers.

## Do not

- Block on single-page crawl for multi-section publishers
- Store crawled page text as LLM system instructions
- Skip persona tag on signal snapshots
