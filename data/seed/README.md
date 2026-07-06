# Gold Label Seed Dataset

Human-reviewed **gold labels** for POC classifier training, crawler spike evaluation, and reviewer console bootstrap. Contains **real domains** with representative page-section URLs.

| Metric | Value |
|--------|-------|
| Records | 615 URLs |
| Domains | 161 unique |
| Batch ID | `seed-v1-2026-07-03` (see `manifest.json`) |
| Labels | `MFA_High` (166), `Non_MFA` (449) |

## Files

| File | Purpose |
|------|---------|
| `gold_labels.csv` | Ad Ops review / spreadsheet import |
| `gold_labels.jsonl` | Machine ingestion (one JSON object per line) |
| `domains_summary.csv` | One row per domain for crawler subset selection |
| `manifest.json` | Record counts, label distribution, provenance |
| `schema/gold_label_record.schema.json` | JSON Schema for validation |

---

## Ingest seed data

Ingestion submits URLs to the backend API as **crawl jobs**. Gold-label metadata (`gold_label`, `label_source`, etc.) stays in the seed files for training and evaluation until a dedicated labels table is added (POC Phase 1).

### Prerequisites

1. **Stack running** — from the repository root:

   ```bash
   docker compose up -d
   curl -s http://localhost:8000/health | jq
   ```

   See the root [`README.md`](../../README.md) for full Docker Compose setup.

2. **Validate seed files** (recommended before ingest):

   ```bash
   python scripts/seed/validate_gold_labels.py
   ```

### Quick smoke test (5 URLs)

```bash
python scripts/seed/ingest_gold_labels.py --limit 5
```

Expected: `accepted=5`, `duplicate=0` on first run. Re-runs show `duplicate=5` (idempotent — same URLs are not re-queued).

### Full dataset (615 URLs)

The API accepts up to **500 URLs per request**. The ingest script batches automatically (2 requests for the full dataset).

```bash
python scripts/seed/ingest_gold_labels.py
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--api-url` | `http://localhost:8000` | Backend base URL |
| `--source-batch-id` | `manifest.version` | Stored on `crawl_jobs.source_batch_id` |
| `--limit N` | all records | Ingest first N URLs only |
| `--subset-domains N` | — | First N domains from `domains_summary.csv` |
| `--write-subset PATH` | — | Save selected URLs to JSON (optional) |
| `--url-file` | `gold_labels.jsonl` | JSON array of URLs (alternative to `--subset-domains`) |
| `--batch-size` | `500` | URLs per API call (max 500) |
| `--priority` | `1` | Crawl job priority (0–100) |
| `--dry-run` | off | Print batch plan without calling API |

### Subset ingest (crawler POC spike)

One command — first 100 domains from `domains_summary.csv`:

```bash
python scripts/seed/ingest_gold_labels.py --subset-domains 100
```

Optional: save the URL list to a file (then ingest from that file later):

```bash
python scripts/seed/ingest_gold_labels.py \
  --subset-domains 100 \
  --write-subset data/seed/subset_100_domains.json \
  --dry-run

python scripts/seed/ingest_gold_labels.py --url-file data/seed/subset_100_domains.json
```

For a precise domain-filtered subset, pass URLs via a small edit to `ingest_gold_labels.py` or split manually with `jq`:

```bash
# First 10 URLs from JSONL
jq -r '.url' data/seed/gold_labels.jsonl | head -10
```

### Manual API call (single batch)

```bash
SOURCE_BATCH_ID=$(jq -r .version data/seed/manifest.json)

curl -s -X POST http://localhost:8000/api/v1/urls \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg batch "$SOURCE_BATCH_ID" \
    --argjson urls "$(jq -s '[.[0:5][].url]' data/seed/gold_labels.jsonl)" \
    '{urls: $urls, source_batch_id: $batch, priority: 1}')" | jq
```

### Verify jobs

Poll a `job_id` from the ingest response:

```bash
curl -s http://localhost:8000/api/v1/jobs/JOB_ID | jq
```

Re-running ingest with the same `source_batch_id` is **idempotent** — duplicate URLs return `duplicate: true` and do not create new crawl jobs. Your smoke test showing `duplicate=5` after a prior run is expected.

### What ingestion does not do (yet)

| Stored via API today | Remains in seed files for now |
|----------------------|-------------------------------|
| `urls` (normalized URL, domain, hash) | `gold_label`, `label_confidence` |
| `crawl_jobs` (status, priority, `source_batch_id`) | `label_source`, `content_category`, `page_type` |
| In-memory crawl queue (POC) | `notes`, `record_id` |

Use `gold_labels.csv` / `gold_labels.jsonl` when training rules + XGBoost or evaluating classifier output.

---

## Regenerate seed files

```bash
python scripts/seed/build_gold_labels.py
python scripts/seed/export_domains_summary.py
python scripts/seed/validate_gold_labels.py
```

## Label distribution

| Label | Count | Description | Source |
|-------|-------|-------------|--------|
| `MFA_High` | 166 | Strong MFA evidence | Adalytics 2024 study (Jounce + DeepSee confirmed), Pixalate MFA report |
| `Non_MFA` | 449 | Legitimate editorial publishers | Established news, tech, sports, health allowlist |

`MFA_Medium` / `MFA_Low` may be added after Ad Ops review (see Next steps).

## Sources

1. **[Adalytics Jan 2024 MFA study](https://adalytics.io/blog/ads-observed-on-made-for-advertising-sites-in-january-2024)** — domains meeting ANA/WFA/ISBA/4A's MFA definition, confirmed by Jounce Media and DeepSee.io (e.g. `globetip.com`, `kueez.com`, `za.investing.com`, `go.reference.com`).
2. **[Pixalate Q1 2024 MFA Report](https://www.pixalate.com/blog/q1-2024-made-for-advertising-websites-report)** — high-spend likely MFA domains (e.g. `iwastesomuchmoney.com`, `thesportsdrop.com`).
3. **Industry MFA coverage** — ExchangeWire, AdExchanger, Campaign US, IAB UK.
4. **Editorial allowlist** — major legitimate publishers across news, technology, sports, health, business, travel.

## Contrast set

Includes **Non_MFA** entries on parent domains (`www.forbes.com`, `www.investing.com`, `www.reference.com`) to train page-section granularity — distinct from known MFA subdomains (`za.investing.com`, `go.reference.com`).

## ML training

- Use `gold_label` as supervised target
- Stratify by `content_category` and `page_type`
- Hold out 20% by **domain** (not URL) to avoid leakage

## Crawler POC spike (POC-2.5)

Run the crawler spike on the first N domains in `domains_summary.csv` (default 100):

```bash
# Full spike — writes crawler/artifacts/crawl_spike/report.json + report.md
uv run --package mfa-crawler python -m mfa_crawler.spike_cli

# Quick smoke (10 domains)
uv run --package mfa-crawler python -m mfa_crawler.spike_cli --domains 10 --delay-sec 0
```

The spike tries multiple seed URLs per domain (article → category → homepage) when paths 404.

Ingest-only domain list (no crawl):

```bash
cut -d, -f1 data/seed/domains_summary.csv | tail -n +2 | head -100
```

## Caveats

- **MFA lists change daily** — Jounce, Pixalate, and SSP blocklists add/remove domains continuously. Re-validate with Ad Ops before production blocking.
- **Representative article paths** — some URLs use typical path patterns; verify HTTP 200 before batch crawl.
- **Not legal advice** — crawling targets requires robots.txt review and legal approval per [`docs/GUARDRAILS.md`](../../docs/GUARDRAILS.md).
- **Subdomain granularity** — score at URL/path level; do not block entire registrable domains when only a subdomain is MFA.

## Validation

### Automated checks

```bash
python scripts/seed/validate_gold_labels.py
```

Validates:

- CSV/JSONL row parity and manifest counts
- Required fields and enums per `schema/gold_label_record.schema.json`
- Minimum label counts (`MFA_High` ≥50, `Non_MFA` ≥50)
- `record_id` format (`gl_[a-f0-9]{16}`)

Last automated run: **2026-07-06** — 615 records OK.

### Ad Ops review status

| Check | Status | Notes |
|-------|--------|-------|
| Automated schema + distribution | ✅ Pass | `validate_gold_labels.py` |
| Stratified sample review (50 URLs) | ⏳ Pending | Export with `head`/`shuf` on `gold_labels.csv` |
| DSP inventory overlap | ⏳ Pending | Confirm seed domains appear in ad ops feeds |
| Formal Ad Ops sign-off | ⏳ Pending | Record approver + date below when complete |

**Approver sign-off** (fill when complete):

```
Reviewer:
Date:
Notes:
```

Until formal sign-off, treat labels as **bootstrap training data** — suitable for crawler spike and model training, not production blocking.

## Next steps

1. Complete Ad Ops sample review (50 URLs stratified by label) and record sign-off above
2. Confirm DSP inventory overlap
3. Ingest seed URLs → run POC crawler on subset → populate `signal_snapshots`
4. Train rules + XGBoost baseline per [`docs/ROADMAP.md`](../../docs/ROADMAP.md)
