import { useMutation } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { submitReviewOverride } from "../api/client";
import {
  FINAL_LABELS,
  OVERRIDE_REASONS,
  type FinalLabel,
  type OverrideReason,
} from "../api/types";
import { ForbiddenBanner } from "../components/ForbiddenBanner";

type OverridePageProps = {
  initialClassificationId?: string;
};

export function OverridePage({ initialClassificationId = "" }: OverridePageProps) {
  const [classificationId, setClassificationId] = useState(initialClassificationId);
  const [finalLabel, setFinalLabel] = useState<FinalLabel>("Non_MFA");
  const [overrideReason, setOverrideReason] =
    useState<OverrideReason>("confirmed_non_mfa");
  const [notes, setNotes] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const overrideMutation = useMutation({
    mutationFn: submitReviewOverride,
    onSuccess: () => {
      setClassificationId("");
      setNotes("");
    },
  });

  useEffect(() => {
    if (initialClassificationId) {
      setClassificationId(initialClassificationId);
    }
  }, [initialClassificationId]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setValidationError(null);
    overrideMutation.reset();

    if (!classificationId.trim()) {
      setValidationError("Classification ID is required.");
      return;
    }

    overrideMutation.mutate({
      classification_id: classificationId.trim(),
      final_label: finalLabel,
      override_reason: overrideReason,
      notes: notes.trim() || undefined,
    });
  }

  const result = overrideMutation.data ?? null;

  return (
    <section>
      <h2 className="page-title">Submit Override</h2>
      <div className="card">
        <form className="form-grid" onSubmit={handleSubmit} noValidate>
          <label htmlFor="classification-id">
            Classification ID
            <input
              id="classification-id"
              type="text"
              value={classificationId}
              onChange={(e) => setClassificationId(e.target.value)}
              placeholder="uuid"
              required
              autoComplete="off"
            />
          </label>

          <label htmlFor="final-label">
            Final label
            <select
              id="final-label"
              value={finalLabel}
              onChange={(e) => setFinalLabel(e.target.value as FinalLabel)}
            >
              {FINAL_LABELS.map((label) => (
                <option key={label} value={label}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label htmlFor="override-reason">
            Override reason
            <select
              id="override-reason"
              value={overrideReason}
              onChange={(e) =>
                setOverrideReason(e.target.value as OverrideReason)
              }
              required
            >
              {OVERRIDE_REASONS.map((reason) => (
                <option key={reason} value={reason}>
                  {reason.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>

          <label htmlFor="notes">
            Notes (optional)
            <textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              maxLength={2000}
            />
          </label>

          <button type="submit" disabled={overrideMutation.isPending}>
            {overrideMutation.isPending ? "Submitting…" : "Submit override"}
          </button>
        </form>

        {validationError && (
          <div className="status error" role="alert" style={{ marginTop: "1rem" }}>
            {validationError}
          </div>
        )}

        {overrideMutation.error && (
          <div style={{ marginTop: "1rem" }}>
            <ForbiddenBanner
              error={overrideMutation.error}
              fallback="Failed to submit override"
            />
          </div>
        )}

        {result && (
          <div className="status success" style={{ marginTop: "1rem" }}>
            Override saved — review ID <code>{result.review_id}</code>, ML tier{" "}
            {result.ml_tier} (score {result.ml_mfa_score.toFixed(3)})
          </div>
        )}
      </div>
    </section>
  );
}
