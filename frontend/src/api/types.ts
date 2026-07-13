export type FinalLabel =
  | "MFA_High"
  | "MFA_Medium"
  | "MFA_Low"
  | "Non_MFA"
  | "Uncertain";

export type OverrideReason =
  | "false_positive_publisher"
  | "referral_delta_expected"
  | "policy_exception"
  | "insufficient_evidence"
  | "vendor_disagreement"
  | "confirmed_mfa"
  | "confirmed_non_mfa";

export type RAGConfidence = "high" | "medium" | "low" | "insufficient";

export type RecommendedAction = "block" | "allow" | "recheck" | "human_review";

export interface ReviewQueueItem {
  url_id: string;
  url: string;
  domain: string;
  classification_id: string;
  tier: string;
  mfa_score: number;
  confidence: string;
  top_signals: unknown[];
  explanation: string;
  evidence_hash: string;
  created_at: string;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReviewOverrideRequest {
  classification_id: string;
  final_label: FinalLabel;
  override_reason: OverrideReason;
  notes?: string;
}

export interface ReviewOverrideResponse {
  review_id: string;
  url_id: string;
  classification_id: string;
  final_label: FinalLabel;
  override_reason: OverrideReason;
  ml_tier: string;
  ml_mfa_score: number;
  evidence_hash: string;
  reviewer_id: string;
  created_at: string;
}

export interface Citation {
  source: string;
  id: string;
  excerpt: string;
}

export interface SignalContribution {
  name: string;
  value?: number | boolean | null;
  contribution?: number | null;
}

export interface RAGResponse {
  answer: string;
  confidence: RAGConfidence;
  citations: Citation[];
  top_signals: SignalContribution[];
  recommended_action: RecommendedAction;
  limitations: string;
}

export interface ChatRequest {
  query: string;
  url_id?: string;
  domain?: string;
}

export interface ApiError {
  error: string;
  code?: string;
  details?: Record<string, unknown>;
}

export interface TopSignalRow {
  feature?: string;
  name?: string;
  value?: unknown;
  contribution?: number;
  rank?: number;
}

export interface AuditEventItem {
  event_id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_id: string;
  occurred_at: string;
  evidence_hash?: string | null;
  payload: Record<string, unknown>;
}

export interface AuditEventListResponse {
  url_id: string;
  items: AuditEventItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface EvidenceArtifactItem {
  version: number;
  persona: string;
  screenshot_url: string;
  page_html_url: string;
  dom_metrics_url: string;
}

export interface EvidenceArtifactListResponse {
  url_id: string;
  artifacts: EvidenceArtifactItem[];
}

export interface BlocklistEntry {
  url: string;
  domain: string;
  tier: string;
  mfa_score: number;
  confidence: string;
  evidence_hash: string;
}

export interface BlocklistResponse {
  entries: BlocklistEntry[];
  total: number;
  limit: number;
  offset: number;
}

export const FINAL_LABELS: FinalLabel[] = [
  "MFA_High",
  "MFA_Medium",
  "MFA_Low",
  "Non_MFA",
  "Uncertain",
];

export const OVERRIDE_REASONS: OverrideReason[] = [
  "false_positive_publisher",
  "referral_delta_expected",
  "policy_exception",
  "insufficient_evidence",
  "vendor_disagreement",
  "confirmed_mfa",
  "confirmed_non_mfa",
];
