import type { MfaRole } from "./types";

export type AppPage = "queue" | "override" | "chat" | "blocklist";

const QUEUE_ROLES: MfaRole[] = ["reviewer", "admin", "ad_ops", "auditor"];
const OVERRIDE_ROLES: MfaRole[] = ["reviewer", "admin", "ad_ops"];
const CHAT_ROLES: MfaRole[] = ["reviewer", "admin", "ad_ops", "auditor", "read_only"];
const BLOCKLIST_ROLES: MfaRole[] = ["admin", "ad_ops", "auditor"];

export function canAccessQueue(role: MfaRole): boolean {
  return QUEUE_ROLES.includes(role);
}

export function canSubmitOverride(role: MfaRole): boolean {
  return OVERRIDE_ROLES.includes(role);
}

export function canAccessChat(role: MfaRole): boolean {
  return CHAT_ROLES.includes(role);
}

export function canAccessBlocklist(role: MfaRole): boolean {
  return BLOCKLIST_ROLES.includes(role);
}

export function canAccessPage(role: MfaRole, page: AppPage): boolean {
  switch (page) {
    case "queue":
      return canAccessQueue(role);
    case "override":
      return canSubmitOverride(role);
    case "chat":
      return canAccessChat(role);
    case "blocklist":
      return canAccessBlocklist(role);
    default:
      return false;
  }
}

export function defaultPageForRole(role: MfaRole): AppPage {
  if (canAccessQueue(role)) return "queue";
  if (canAccessBlocklist(role)) return "blocklist";
  if (canAccessChat(role)) return "chat";
  return "queue";
}

export function navItemsForRole(role: MfaRole): { id: AppPage; label: string }[] {
  const items: { id: AppPage; label: string }[] = [];
  if (canAccessQueue(role)) {
    items.push({ id: "queue", label: "Review Queue" });
  }
  if (canSubmitOverride(role)) {
    items.push({ id: "override", label: "Override" });
  }
  if (canAccessChat(role)) {
    items.push({ id: "chat", label: "Chat" });
  }
  if (canAccessBlocklist(role)) {
    items.push({ id: "blocklist", label: "Blocklist" });
  }
  return items;
}
