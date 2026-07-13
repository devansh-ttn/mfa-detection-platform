export const queryKeys = {
  reviewQueue: (tier: string[], domain: string) =>
    ["reviewQueue", { tier, domain }] as const,
  auditEvents: (urlId: string) => ["auditEvents", urlId] as const,
  evidenceArtifacts: (urlId: string) => ["evidenceArtifacts", urlId] as const,
  blocklist: (tier: string[], domain: string, offset: number) =>
    ["blocklist", { tier, domain, offset }] as const,
};
