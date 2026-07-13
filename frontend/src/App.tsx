import { useEffect, useState } from "react";
import { useAuth } from "./auth/AuthContext";
import {
  canAccessPage,
  defaultPageForRole,
  navItemsForRole,
  type AppPage,
} from "./auth/permissions";
import { BlocklistPage } from "./pages/BlocklistPage";
import { ChatPage } from "./pages/ChatPage";
import { CognitoLoginPage } from "./pages/CognitoLoginPage";
import { DevLoginPage } from "./pages/DevLoginPage";
import { OverridePage } from "./pages/OverridePage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";

export default function App() {
  const { session, logout, loading, cognitoEnabled } = useAuth();
  const [page, setPage] = useState<AppPage>(() =>
    session ? defaultPageForRole(session.role) : "queue",
  );
  const [overrideClassificationId, setOverrideClassificationId] = useState("");

  useEffect(() => {
    if (!session) return;
    if (!canAccessPage(session.role, page)) {
      setPage(defaultPageForRole(session.role));
    }
  }, [session, page]);

  useEffect(() => {
    if (page !== "override") {
      setOverrideClassificationId("");
    }
  }, [page]);

  if (loading) {
    return (
      <div className="login-shell">
        <p className="muted-text" aria-live="polite">
          Loading session…
        </p>
      </div>
    );
  }

  if (!session) {
    return cognitoEnabled ? <CognitoLoginPage /> : <DevLoginPage />;
  }

  const nav = navItemsForRole(session.role);

  function navigateToOverride(classificationId: string) {
    setOverrideClassificationId(classificationId);
    setPage("override");
  }

  return (
    <>
      <header className="app-header">
        <h1>MFA Review Console</h1>
        <nav className="app-nav" aria-label="Main navigation">
          {nav.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              className={page === id ? "active" : ""}
              aria-current={page === id ? "page" : undefined}
              onClick={() => setPage(id)}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="app-user">
          <span className="user-pill" title={`Actor: ${session.actor}`}>
            {session.role.replace(/_/g, " ")} · {session.actor}
          </span>
          <button type="button" className="link-button" onClick={() => void logout()}>
            Sign out
          </button>
        </div>
      </header>
      <main>
        {page === "queue" && canAccessPage(session.role, "queue") && (
          <ReviewQueuePage
            onSelectOverride={navigateToOverride}
            canOverride={canAccessPage(session.role, "override")}
          />
        )}
        {page === "override" && canAccessPage(session.role, "override") && (
          <OverridePage initialClassificationId={overrideClassificationId} />
        )}
        {page === "chat" && canAccessPage(session.role, "chat") && <ChatPage />}
        {page === "blocklist" && canAccessPage(session.role, "blocklist") && (
          <BlocklistPage />
        )}
      </main>
    </>
  );
}
