import type { AuthSession } from "./types";

const DEV_STORAGE_KEY = "mfa-dev-auth";

export function loadDevAuthSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(DEV_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed.role || !parsed.actor?.trim()) return null;
    return {
      role: parsed.role,
      actor: parsed.actor.trim(),
      mode: "dev",
    };
  } catch {
    return null;
  }
}

export function saveDevAuthSession(session: AuthSession): void {
  localStorage.setItem(
    DEV_STORAGE_KEY,
    JSON.stringify({ role: session.role, actor: session.actor }),
  );
}

export function clearDevAuthSession(): void {
  localStorage.removeItem(DEV_STORAGE_KEY);
}
