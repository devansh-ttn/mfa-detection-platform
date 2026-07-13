import { FormEvent, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { MFA_ROLES, type MfaRole } from "../auth/types";

export function DevLoginPage() {
  const { loginDev } = useAuth();
  const [role, setRole] = useState<MfaRole>("reviewer");
  const [actor, setActor] = useState("local-reviewer");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = actor.trim();
    if (!trimmed) {
      setError("Actor name is required.");
      return;
    }
    setError(null);
    loginDev(role, trimmed);
  }

  return (
    <div className="login-shell">
      <section className="card login-card">
        <h1 className="page-title">MFA Review Console</h1>
        <p className="login-subtitle">
          Local dev login — pick a role and actor name. Sent as{" "}
          <code>X-MFA-Role</code> / <code>X-MFA-Actor</code> (disabled when Cognito
          env vars are set).
        </p>
        <form className="form-grid" onSubmit={handleSubmit} noValidate>
          <label htmlFor="dev-role">
            Role
            <select
              id="dev-role"
              value={role}
              onChange={(e) => setRole(e.target.value as MfaRole)}
            >
              {MFA_ROLES.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label htmlFor="dev-actor">
            Actor name
            <input
              id="dev-actor"
              type="text"
              value={actor}
              onChange={(e) => setActor(e.target.value)}
              placeholder="your-name"
              required
              autoComplete="username"
            />
          </label>

          <button type="submit">Continue</button>
        </form>

        {error && (
          <div className="status error" role="alert" style={{ marginTop: "1rem" }}>
            {error}
          </div>
        )}
      </section>
    </div>
  );
}
