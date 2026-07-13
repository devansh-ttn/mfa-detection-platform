import { useMutation } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import type { ChatRequest } from "../api/types";
import { postChat } from "../api/client";
import { ForbiddenBanner } from "../components/ForbiddenBanner";

export function ChatPage() {
  const [query, setQuery] = useState("");
  const [urlId, setUrlId] = useState("");
  const [domain, setDomain] = useState("");

  const chatMutation = useMutation({
    mutationFn: (body: ChatRequest) => postChat(body),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    chatMutation.reset();
    chatMutation.mutate({
      query: trimmed,
      url_id: urlId.trim() || undefined,
      domain: domain.trim() || undefined,
    });
  }

  const response = chatMutation.data ?? null;

  return (
    <section>
      <h2 className="page-title">RAG Chat</h2>
      <div className="card">
        <form className="form-grid" onSubmit={handleSubmit} noValidate>
          <label htmlFor="chat-query">
            Question
            <textarea
              id="chat-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={3}
              placeholder="Why is this URL classified as MFA?"
              required
            />
          </label>

          <label htmlFor="chat-url-id">
            URL ID (optional)
            <input
              id="chat-url-id"
              type="text"
              value={urlId}
              onChange={(e) => setUrlId(e.target.value)}
              autoComplete="off"
            />
          </label>

          <label htmlFor="chat-domain">
            Domain (optional)
            <input
              id="chat-domain"
              type="text"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              autoComplete="off"
            />
          </label>

          <button type="submit" disabled={chatMutation.isPending}>
            {chatMutation.isPending ? "Asking…" : "Ask"}
          </button>
        </form>

        {chatMutation.error && (
          <div style={{ marginTop: "1rem" }}>
            <ForbiddenBanner error={chatMutation.error} fallback="Chat request failed" />
          </div>
        )}

        {response && (
          <article style={{ marginTop: "1.5rem" }} aria-live="polite">
            <div className="meta-row">
              <span className="meta-pill">
                Confidence: <strong>{response.confidence}</strong>
              </span>
              <span className="meta-pill">
                Action: <strong>{response.recommended_action}</strong>
              </span>
            </div>

            <div className="answer-text">{response.answer}</div>

            {response.top_signals.length > 0 && (
              <div style={{ marginTop: "1rem" }}>
                <h3 style={{ margin: "0 0 0.5rem", fontSize: "0.9rem" }}>
                  Top signals
                </h3>
                <ul style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "0.875rem" }}>
                  {response.top_signals.map((signal) => (
                    <li key={signal.name}>
                      {signal.name}
                      {signal.value != null && ` = ${String(signal.value)}`}
                      {signal.contribution != null &&
                        ` (contribution ${signal.contribution.toFixed(2)})`}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {response.citations.length > 0 && (
              <div className="citations">
                <h3>Citations</h3>
                {response.citations.map((citation) => (
                  <div key={citation.id} className="citation-item">
                    <a
                      href={`#citation-${citation.id}`}
                      id={`citation-${citation.id}`}
                      title={citation.excerpt}
                    >
                      [{citation.source}] {citation.id}
                    </a>
                    <p className="citation-excerpt">{citation.excerpt}</p>
                  </div>
                ))}
              </div>
            )}

            {response.limitations && (
              <p
                style={{
                  marginTop: "1rem",
                  fontSize: "0.8125rem",
                  color: "#64748b",
                }}
              >
                Limitations: {response.limitations}
              </p>
            )}
          </article>
        )}
      </div>
    </section>
  );
}
