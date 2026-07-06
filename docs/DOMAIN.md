# MFA Platform — Domain Glossary

## MFA (Made-For-Advertising)

Websites engineered primarily to arbitrage ad impressions via bought traffic, high ad density, refresh recycling, and thin content — not legitimate editorial publishing.

## Classification tiers

| Tier | Meaning | Default action |
|------|---------|----------------|
| `MFA_High` | Strong multi-signal MFA evidence | Block |
| `MFA_Medium` | Probable MFA; needs judgment | Human review |
| `MFA_Low` | Weak signals; monitor | Monitor |
| `Non_MFA` | Legitimate publisher patterns | Allow |
| `Uncertain` | Conflicting or insufficient evidence | Human review |

## Key entities

| Entity | Description |
|--------|-------------|
| `url_id` | Normalized URL identifier (path-level, not domain-only) |
| `signal_snapshot` | Versioned feature vector + raw metrics for a crawl |
| `classification` | Scoring event: tier, score, confidence, top_signals |
| `evidence_hash` | Content hash of signal snapshot for audit correlation |
| `reviewer_override` | Human `final_label` + `override_reason` (does not delete ML score) |

## Signal tiers (research)

**Tier 1 (highest value):** ad density/clutter, ad refresh behavior, traffic source skew, referral vs direct persona delta, content quality

**Tier 2 (supporting):** domain metadata, authority/SEO, page-level section scoring, supply chain (sellers.json, ads.txt), campaign performance anomalies

**Tier 3 (contextual):** reviewer overrides, historical versions, block/allow lists, industry reference lists (bootstrap only)

## Signals to treat cautiously

- Viewability alone (MFA often scores high)
- IVT/fraud flags alone (MFA traffic is often human)
- Homepage-only crawl (deep-link articles)
- Single-domain block (subdomains and seller nodes matter)

## Ad ops terms

| Term | Meaning |
|------|---------|
| DSP | Demand-side platform — inventory source |
| SSP | Supply-side platform |
| OpenRTB | Real-time bidding protocol |
| sellers.json | SSP publisher transparency file |
| ads.txt | Authorized digital sellers list |
| HITL | Human-in-the-loop review queue |
