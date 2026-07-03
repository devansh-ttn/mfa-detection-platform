# MFA Detection Platform

AI-enabled **Made-For-Advertising (MFA)** detection platform with explainable classification, human-in-the-loop review, and a RAG conversational bot.

## Status

Architecture approved — pre-implementation. See the full lead architect report in [`.cursor/plans/mfa_platform_architecture_48645023.plan.md`](.cursor/plans/mfa_platform_architecture_48645023.plan.md).

## For Cursor AI

| Resource | Purpose |
|----------|---------|
| [`AGENTS.md`](AGENTS.md) | Agent entry point — mission, stack, workflow |
| [`docs/`](docs/) | Architecture, domain, ADRs, signals, RAG, roadmap, guardrails |
| [`.cursor/rules/`](.cursor/rules/) | 8 layer-specific rules (core, security, ML, RAG, crawler, API, infra, UI) |
| [`.cursor/skills/`](.cursor/skills/) | 6 workflow skills (platform, signals, classifier, crawler, RAG, ADR) |
| [`.cursor/agents/`](.cursor/agents/) | 6 specialized subagents (architect, ML, RAG, crawler, security, UI) |

### Subagents

Invoke via Cursor chat, e.g.:

- `Use the mfa-architect subagent to review this design`
- `Use the mfa-crawler-engineer subagent to plan the POC spike`
- `Use the mfa-security-reviewer subagent on the RAG PR`

## Roadmap phases

| Phase | Focus |
|-------|-------|
| **POC** (6–8 wk) | Rules + XGBoost, single-persona crawl, Postgres, template explanations |
| **MVP** (+10–12 wk) | Dual-persona, LLM explanations, RAG v1, review console, OpenSearch |
| **Production** (+12–16 wk) | Near-real-time, pre-bid API, auto-retrain, SSO, multi-region |

Details: [`docs/ROADMAP.md`](docs/ROADMAP.md)

## Core design principles

1. **Hybrid ML + LLM** — rules + XGBoost classify; LLM explains and powers RAG only
2. **Page-section granularity** — score URL paths, not domains alone
3. **Versioned evidence** — immutable signal snapshots for audit and RAG grounding
4. **Retrieve-first RAG** — citation validator on every answer

## License

Internal assessment project.
