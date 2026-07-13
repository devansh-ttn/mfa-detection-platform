/** RBAC roles — must match backend `mfa.auth.roles.Role`. */
export type MfaRole =
  | "admin"
  | "reviewer"
  | "ad_ops"
  | "auditor"
  | "read_only";

export const MFA_ROLES: { value: MfaRole; label: string }[] = [
  { value: "reviewer", label: "Reviewer" },
  { value: "admin", label: "Admin" },
  { value: "ad_ops", label: "Ad Ops" },
  { value: "auditor", label: "Auditor" },
  { value: "read_only", label: "Read only" },
];

export type AuthMode = "cognito" | "dev";

export interface AuthSession {
  role: MfaRole;
  actor: string;
  mode: AuthMode;
  /** Cognito ID token sent as Authorization Bearer (deployed MVP). */
  idToken?: string;
}
