import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { fetchEvidenceBlob, getEvidenceArtifacts } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { ForbiddenBanner } from "./ForbiddenBanner";

type EvidenceThumbnailsProps = {
  urlId: string;
};

function AuthenticatedScreenshot({
  screenshotPath,
  label,
}: {
  screenshotPath: string;
  label: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    void fetchEvidenceBlob(screenshotPath)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setError("Screenshot unavailable");
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [screenshotPath]);

  if (error) {
    return <p className="muted-text">{error}</p>;
  }
  if (!src) {
    return <p className="muted-text">Loading screenshot…</p>;
  }

  return (
    <a href={src} target="_blank" rel="noopener noreferrer">
      <img
        src={src}
        alt={`Evidence screenshot — ${label}`}
        className="evidence-thumb"
        loading="lazy"
      />
    </a>
  );
}

export function EvidenceThumbnails({ urlId }: EvidenceThumbnailsProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.evidenceArtifacts(urlId),
    queryFn: () => getEvidenceArtifacts(urlId),
  });

  if (isLoading) {
    return <p className="muted-text">Loading evidence artifacts…</p>;
  }
  if (error) {
    return (
      <ForbiddenBanner error={error} fallback="Failed to load evidence" />
    );
  }
  if (!data?.artifacts.length) {
    return (
      <p className="muted-text">
        No local evidence artifacts for this URL (crawl may not have completed).
      </p>
    );
  }

  return (
    <div className="evidence-grid">
      {data.artifacts.map((artifact) => (
        <figure key={artifact.version} className="evidence-card">
          <figcaption>
            v{artifact.version} · {artifact.persona}
          </figcaption>
          <AuthenticatedScreenshot
            screenshotPath={artifact.screenshot_url}
            label={`v${artifact.version} ${artifact.persona}`}
          />
        </figure>
      ))}
    </div>
  );
}
