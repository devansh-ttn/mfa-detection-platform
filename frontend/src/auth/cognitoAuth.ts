import { UserManager, WebStorageStateStore } from "oidc-client-ts";
import { getCognitoConfig } from "./cognitoConfig";

let userManager: UserManager | null = null;

export function getUserManager(): UserManager | null {
  const config = getCognitoConfig();
  if (!config) {
    return null;
  }

  if (!userManager) {
    userManager = new UserManager({
      authority: config.authority,
      client_id: config.clientId,
      redirect_uri: config.redirectUri,
      post_logout_redirect_uri: config.redirectUri,
      response_type: "code",
      scope: "openid email profile",
      userStore: new WebStorageStateStore({ store: window.sessionStorage }),
      automaticSilentRenew: true,
    });
  }

  return userManager;
}
