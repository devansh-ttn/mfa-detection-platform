import { useAuth } from "../auth/AuthContext";

export function CognitoLoginPage() {
  const { loginCognito, authError } = useAuth();

  return (
    <div className="login-shell">
      <section className="card login-card">
        <h1 className="page-title">MFA Review Console</h1>
        <p className="login-subtitle">
          Sign in with your organization account. Access is controlled by Cognito
          groups mapped to MFA roles (admin, reviewer, ad_ops, auditor,
          read_only).
        </p>
        <button type="button" className="btn-primary" onClick={() => void loginCognito()}>
          Sign in
        </button>
        {authError && (
          <div className="status error" role="alert" style={{ marginTop: "1rem" }}>
            {authError}
          </div>
        )}
      </section>
    </div>
  );
}
