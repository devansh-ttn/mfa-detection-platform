---
name: mfa-rag-bot
description: Implements the MFA RAG bot with hybrid SQL + OpenSearch retrieval, citation validation, and grounded response contract. Use when building chat API, retrievers, chunk indexing, query routing, or anti-hallucination pipelines.
---

# MFA RAG Bot Implementation

## Reference

`docs/RAG.md` · `.cursor/rules/mfa-rag.mdc`

## Implementation checklist

```
- [ ] Index corpora with doc_type metadata (signal_snapshot, explanation, policy, reviewer_note, audit)
- [ ] Build query router (intent → SQL vs vector vs diff)
- [ ] Implement evidence packager (merge SQL + vector results)
- [ ] Grounded LLM with structured output schema
- [ ] Citation validator post-generation
- [ ] Audit log every query + response + evidence_hash
```

## Response schema (enforce in code)

```python
class RAGResponse(BaseModel):
    answer: str
    confidence: Literal["high", "medium", "low", "insufficient"]
    citations: list[Citation]
    top_signals: list[SignalContribution]
    recommended_action: Literal["block", "allow", "recheck", "human_review"]
    limitations: str
```

## Query routing table

| Intent | Tools |
|--------|-------|
| explain_classification | SQL: classifications + signal_snapshots |
| signal_attribution | SQL: top_signals / SHAP |
| change_since_review | SQL: diff snapshots by version |
| similar_sites | OpenSearch k-NN (v2 only) |
| policy_lookup | OpenSearch BM25 on policy chunks |

## Anti-hallucination

1. Empty evidence pack → return `insufficient` without LLM call
2. Validator maps each sentence to citation ID
3. Conflicting evidence → `recommended_action: human_review`

## MVP scope

> **TODO(MVP):** SQL + vector over signals, policies, classifications. Similar-domain search deferred to Production (RAG v2).
