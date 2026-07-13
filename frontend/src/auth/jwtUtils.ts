import type { MfaRole } from "./types";

const ROLE_PRIORITY: MfaRole[] = [
  "admin",
  "reviewer",
  "ad_ops",
  "auditor",
  "read_only",
];

export function parseJwtPayload(token: string): Record<string, unknown> {
  const segment = token.split(".")[1];
  if (!segment) {
    throw new Error("Invalid JWT");
  }
  const normalized = segment.replace(/-/g, "+").replace(/_/g, "/");
  const json = atob(normalized);
  return JSON.parse(json) as Record<string, unknown>;
}

export function resolveRoleFromToken(token: string): MfaRole | null {
  const payload = parseJwtPayload(token);
  const groupsRaw = payload["cognito:groups"];
  const groups = Array.isArray(groupsRaw)
    ? groupsRaw.map(String)
    : typeof groupsRaw === "string"
      ? [groupsRaw]
      : [];

  const normalized = new Set(groups.map((g) => g.toLowerCase()));
  for (const role of ROLE_PRIORITY) {
    if (normalized.has(role)) {
      return role;
    }
  }
  return null;
}

export function actorFromToken(token: string): string {
  const payload = parseJwtPayload(token);
  for (const key of ["email", "username", "cognito:username", "sub"]) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "unknown";
}
