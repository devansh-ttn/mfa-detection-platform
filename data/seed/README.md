# Gold Label Seed Dataset

Human-reviewed **gold labels** for POC classifier training, crawler spike evaluation, and reviewer console bootstrap. Contains **real domains** with representative page-section URLs.

## Files

| File | Purpose |
|------|---------|
| `gold_labels.csv` | Ad Ops review / spreadsheet import |
| `gold_labels.jsonl` | Machine ingestion (one JSON object per line) |
| `domains_summary.csv` | One row per domain for crawler subset selection |
| `manifest.json` | Record counts, label distribution, provenance |
| `schema/gold_label_record.schema.json` | JSON Schema for validation |

## Regenerate

```bash
python scripts/seed/build_gold_labels.py
```

## Label distribution (target)

| Label | Description | Source |
|-------|-------------|--------|
| `MFA_High` | Strong MFA evidence | Adalytics 2024 study (Jounce + DeepSee confirmed), Pixalate MFA report |
| `MFA_Medium` | Borderline / mixed quality | Industry coverage, manual contrast cases |
| `Non_MFA` | Legitimate editorial publishers | Established news, tech, sports, health allowlist |

## Sources

1. **[Adalytics Jan 2024 MFA study](https://adalytics.io/blog/ads-observed-on-made-for-advertising-sites-in-january-2024)** — domains meeting ANA/WFA/ISBA/4A's MFA definition, confirmed by Jounce Media and DeepSee.io (e.g. `globetip.com`, `kueez.com`, `za.investing.com`, `go.reference.com`).
2. **[Pixalate Q1 2024 MFA Report](https://www.pixalate.com/blog/q1-2024-made-for-advertising-websites-report)** — high-spend likely MFA domains (e.g. `iwastesomuchmoney.com`, `thesportsdrop.com`).
3. **Industry MFA coverage** — ExchangeWire, AdExchanger, Campaign US, IAB UK.
4. **Editorial allowlist** — major legitimate publishers across news, technology, sports, health, business, travel.

## Contrast set

Includes **Non_MFA** entries on parent domains (`www.forbes.com`, `www.investing.com`, `www.reference.com`) to train page-section granularity — distinct from known MFA subdomains (`za.investing.com`, `go.reference.com`).

## Usage

### Ingestion API (planned)

```bash
# POST /api/v1/urls with source_batch_id from manifest
curl -X POST /api/v1/urls \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://globetip.com/news/..."], "source_batch_id": "seed-v1-2026-07-03"}'
```

### ML training

- Use `gold_label` as supervised target
- Stratify by `content_category` and `page_type`
- Hold out 20% by **domain** (not URL) to avoid leakage

### Crawler POC spike

Per `.cursor/skills/mfa-crawler/SKILL.md`: run dual-persona crawl on a 100-domain subset:

```bash
cut -d, -f3 data/seed/gold_labels.csv | tail -n +2 | sort -u | head -100
```

## Caveats

- **MFA lists change daily** — Jounce, Pixalate, and SSP blocklists add/remove domains continuously. Re-validate with Ad Ops before production blocking.
- **Representative article paths** — some URLs use typical path patterns; verify HTTP 200 before batch crawl.
- **Not legal advice** — crawling targets requires robots.txt review and legal approval per `docs/GUARDRAILS.md`.
- **Subdomain granularity** — score at URL/path level; do not block entire registrable domains when only a subdomain is MFA.

## Validation

```bash
python scripts/seed/validate_gold_labels.py
```

## Next steps

1. Ad Ops review sample (50 URLs stratified by label)
2. Confirm DSP inventory overlap
3. Run POC crawler on subset → populate `signal_snapshots`
4. Train rules + XGBoost baseline per `docs/ROADMAP.md`
