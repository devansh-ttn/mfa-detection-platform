# MFA Platform — RAG Bot Design

## Query routing

| Query type | Retrieval path |
|------------|----------------|
| "Why is X MFA?" | SQL: latest classification + top_signals + explanation |
| "Which signals contributed most?" | SHAP / feature attribution from signal store |
| "What changed since last review?" | Diff two `signal_snapshot` versions |
| "Show similar MFA websites" | Embedding k-NN with `tier IN (High, Medium)` |
| "What evidence supports Non-MFA?" | Contradicting signals + reviewer overrides |

## Corpus chunking

| doc_type | Chunking | Metadata filters |
|----------|----------|------------------|
| `signal_snapshot` | One doc per url_id+version | `domain`, `url`, `crawl_ts` |
| `explanation` | Per classification event | `classification_id`, `tier` |
| `policy` | 500-token overlapping chunks | `policy_version` |
| `reviewer_note` | Per review event | `reviewer_id`, `domain` |
| `audit` | Immutable event records | `entity_id`, `action` |

## Response contract (required)

```json
{
  "answer": "...",
  "confidence": "high|medium|low|insufficient",
  "citations": [{"source": "signal_snapshot", "id": "...", "excerpt": "..."}],
  "top_signals": [{"name": "ad_to_content_ratio", "value": 0.42, "contribution": 0.31}],
  "recommended_action": "block|allow|recheck|human_review",
  "limitations": "..."
}
```

## Anti-hallucination pipeline

1. Retrieve-first — no generation without evidence pack
2. Citation validator — every claim maps to retrieved chunk ID
3. Retrieval score below threshold → `insufficient evidence` + escalate
4. Conflicting signals → present both sides; default `human_review`

## MVP scope (RAG v1)

- Hybrid SQL (Postgres) + vector (OpenSearch) over signals, policies, classifications
- No similar-domain search until RAG v2 (Production phase)
