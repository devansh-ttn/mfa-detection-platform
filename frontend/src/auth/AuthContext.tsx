import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { setAuthHeaderProvider } from "../api/client";
import { getUserManager } from "./cognitoAuth";
import { isCognitoAuthEnabled } from "./cognitoConfig";
import { actorFromToken, resolveRoleFromToken } from "./jwtUtils";
import { clearDevAuthSession, loadDevAuthSession, saveDevAuthSession } from "./storage";
import type { AuthSession, MfaRole } from "./types";

interface AuthContextValue {
  session: AuthSession | null;
  loading: boolean;
  authError: string | null;
  /** Local dev only — role/actor headers when Cognito is not configured. */
  loginDev: (role: MfaRole, actor: string) => void;
  /** Redirect to Cognito hosted UI. */
  loginCognito: () => Promise<void>;
  logout: () => Promise<void>;
  cognitoEnabled: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function sessionFromIdToken(idToken: string): AuthSession | null {
  const role = resolveRoleFromToken(idToken);
  if (!role) {
    return null;
  }
  return {
    role,
    actor: actorFromToken(idToken),
    mode: "cognito",
    idToken,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const cognitoEnabled = isCognitoAuthEnabled();
  const [session, setSession] = useState<AuthSession | null>(() =>
    cognitoEnabled ? null : loadDevAuthSession(),
  );
  const [loading, setLoading] = useState(cognitoEnabled);
  const [authError, setAuthError] = useState<string | null>(null);

  const loginDev = useCallback((role: MfaRole, actor: string) => {
    const next: AuthSession = { role, actor: actor.trim(), mode: "dev" };
    saveDevAuthSession(next);
    setSession(next);
    setAuthError(null);
  }, []);

  const loginCognito = useCallback(async () => {
    const manager = getUserManager();
    if (!manager) return;
    setAuthError(null);
    await manager.signinRedirect();
  }, []);

  const logout = useCallback(async () => {
    if (session?.mode === "cognito") {
      const manager = getUserManager();
      if (manager) {
        await manager.signoutRedirect();
      }
    } else {
      clearDevAuthSession();
      setSession(null);
    }
  }, [session?.mode]);

  useEffect(() => {
    if (!cognitoEnabled) {
      setLoading(false);
      return;
    }

    const manager = getUserManager();
    if (!manager) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function bootstrap() {
      try {
        if (window.location.search.includes("code=")) {
          const user = await manager!.signinRedirectCallback();
          window.history.replaceState({}, "", window.location.pathname);
          if (user.id_token) {
            const next = sessionFromIdToken(user.id_token);
            if (!next) {
              setAuthError(
                "Signed in, but no MFA role group found. Ask an admin to assign a Cognito group.",
              );
            } else if (!cancelled) {
              setSession(next);
            }
          }
        } else {
          const user = await manager!.getUser();
          if (user?.id_token && !user.expired) {
            const next = sessionFromIdToken(user.id_token);
            if (!next) {
              setAuthError(
                "No MFA role group on your account. Required: admin, reviewer, ad_ops, auditor, or read_only.",
              );
            } else if (!cancelled) {
              setSession(next);
            }
          }
        }
      } catch {
        if (!cancelled) {
          setAuthError("Authentication failed. Try signing in again.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void bootstrap();

    const onUserLoaded = (user: { id_token?: string }) => {
      if (user.id_token) {
        const next = sessionFromIdToken(user.id_token);
        if (next) {
          setSession(next);
          setAuthError(null);
        }
      }
    };

    const onUserUnloaded = () => {
      setSession(null);
    };

    manager.events.addUserLoaded(onUserLoaded);
    manager.events.addUserUnloaded(onUserUnloaded);

    return () => {
      cancelled = true;
      manager.events.removeUserLoaded(onUserLoaded);
      manager.events.removeUserUnloaded(onUserUnloaded);
    };
  }, [cognitoEnabled]);

  useEffect(() => {
    setAuthHeaderProvider(() => {
      if (!session) return {} as Record<string, string>;
      if (session.mode === "cognito" && session.idToken) {
        return { Authorization: `Bearer ${session.idToken}` };
      }
      if (session.mode === "dev") {
        return {
          "X-MFA-Role": session.role,
          "X-MFA-Actor": session.actor,
        };
      }
      return {} as Record<string, string>;
    });
  }, [session]);

  const value = useMemo(
    () => ({
      session,
      loading,
      authError,
      loginDev,
      loginCognito,
      logout,
      cognitoEnabled,
    }),
    [session, loading, authError, loginDev, loginCognito, logout, cognitoEnabled],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
