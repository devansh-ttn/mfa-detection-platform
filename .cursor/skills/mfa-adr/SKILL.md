---
name: mfa-adr
description: Authors and updates Architecture Decision Records for the MFA platform. Use when making build-vs-buy choices, selecting cloud services, changing ML/vector/orchestration strategy, or documenting trade-offs.
---

# MFA ADR Authoring

## Reference

`docs/ADRS.md` — existing ADR-001 through ADR-009

## When to write an ADR

- New model approach, vector store, or orchestration pattern
- Build vs buy decision (crawler, enrichment, verification vendor)
- Cloud service selection or multi-cloud change
- Breaking change to classification contract or signal schema

## Template

```markdown
## ADR-NNN: Title

**Status:** Proposed | Accepted | Deprecated

**Decision:** One sentence.

**Context:** What forces this decision?

**Rationale:** Why this over alternatives?

**Alternatives considered:** List with rejection reasons.

**Consequences:** Positive and negative outcomes.

**Compliance:** Impact on guardrails, audit, cost.
```

## Numbering

Next ADR: ADR-010 (check `docs/ADRS.md` for latest)

## Constraints (do not override without new ADR)

- ADR-001: No LLM-only classification
- ADR-002: Page-section granularity
- ADR-004: OpenSearch for vector — TODO(MVP); see `docs/ROADMAP.md`

Update `docs/ADRS.md` and reference from `AGENTS.md` if mission-impacting.
