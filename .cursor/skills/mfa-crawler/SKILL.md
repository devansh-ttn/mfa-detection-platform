---
name: mfa-crawler
description: Builds the dual-persona Playwright crawler for ad density, refresh detection, and DOM signal extraction. Use when implementing crawl workers, DOM parsers, persona simulation, or the 100-domain POC spike.
---

# MFA Crawler

## Reference

`docs/ADRS.md` (ADR-003) · `docs/SIGNALS.md` · `.cursor/rules/mfa-crawler.mdc`

## POC spike workflow

```
- [ ] Select 100 known MFA + non-MFA domains (gold labels)
- [ ] Implement single-persona crawl (POC) or dual-persona (MVP)
- [ ] 60s dwell with refresh event listener
- [ ] Extract DOM metrics → signals JSONB
- [ ] Capture screenshot + HTML to S3
- [ ] Report: ad density distribution, refresh rate, precision lift vs baseline
```

## Dual-persona setup

```python
PERSONAS = {
    "direct": {"referrer": None},
    "referral": {"referrer": "https://www.outbrain.com/"},  # or Taboola
}
```

Run both per URL; compute delta features.

## DOM extraction targets

`ad_to_content_ratio`, `ads_above_fold`, `ad_slots_count`, `sticky_ad_count`, `video_autoplay_count`, `page_load_ad_latency_ms`

## Worker deployment

SQS message → ECS Fargate worker → write signal_snapshot → enqueue scoring job

## Legal / ethics

Respect robots.txt (configurable). Rate limit per domain. Identify user-agent.
