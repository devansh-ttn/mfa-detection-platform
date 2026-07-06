---
name: mfa-crawler
description: Builds the Playwright crawler for ad density, refresh detection, and DOM signal extraction. Use when implementing crawl workers, DOM parsers, persona simulation, or the 100-domain evaluation spike.
---

# MFA Crawler

## Reference

`docs/ADRS.md` (ADR-003) · `docs/SIGNALS.md` · `backend/src/mfa/schemas/signals.py` · `.cursor/rules/mfa-crawler.mdc`

## Crawler spike workflow

```
- [ ] Select 100 known MFA + non-MFA domains (gold labels / domains_summary.csv)
- [ ] Implement direct-persona crawl (referral persona: TODO(MVP))
- [ ] Dwell + refresh listener (60s target; null until wired — see SIGNALS.md)
- [ ] Extract DOM metrics → SignalFeatures → signal_snapshots JSONB
- [ ] Capture screenshot + HTML to evidence path (S3: TODO(MVP))
- [ ] Report: ad density distribution, refresh rate, precision lift vs baseline
```

## Persona setup

```python
PERSONAS = {
    "direct": {"referrer": None},
    # TODO(MVP): enable referral persona
    "referral": {"referrer": "https://www.outbrain.com/"},  # or Taboola
}
```

Run both per URL when dual-persona ships; compute delta features.

## DOM extraction targets

Persist as `SignalFeatures` fields: `ad_to_content_ratio`, `ads_above_fold`, `ad_slots_count`, `sticky_ad_count`, `video_autoplay_count`, `page_load_ad_latency_ms`

Wrap in `SignalSnapshotPayload` with `schema_version: v1` and `crawl_ts`.

## Worker deployment

Queue message → worker → write `signal_snapshot` → enqueue scoring job

> **TODO(MVP):** Replace in-memory queue with SQS; ECS Fargate workers.

## Legal / ethics

Respect robots.txt (configurable). Rate limit per domain. Identify user-agent.
