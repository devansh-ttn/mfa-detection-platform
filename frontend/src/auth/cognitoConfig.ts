/** Cognito OIDC configuration (MVP-4.6). */

export interface CognitoConfig {
  region: string;
  userPoolId: string;
  clientId: string;
  authority: string;
  redirectUri: string;
}

export function getCognitoConfig(): CognitoConfig | null {
  const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID?.trim();
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID?.trim();
  const region = import.meta.env.VITE_COGNITO_REGION?.trim() || "us-east-1";

  if (!userPoolId || !clientId) {
    return null;
  }

  return {
    region,
    userPoolId,
    clientId,
    authority: `https://cognito-idp.${region}.amazonaws.com/${userPoolId}`,
    redirectUri:
      import.meta.env.VITE_COGNITO_REDIRECT_URI?.trim() ||
      window.location.origin,
  };
}

export function isCognitoAuthEnabled(): boolean {
  return getCognitoConfig() !== null;
}

/** Dev header auth only when Cognito is not configured. */
export function isDevHeaderAuthEnabled(): boolean {
  return !isCognitoAuthEnabled();
}
