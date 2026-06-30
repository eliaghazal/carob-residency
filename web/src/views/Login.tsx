import { type FormEvent, useState } from "react";
import { api, ApiError, session, type Staff } from "../api";

export function Login({ onLogin }: { onLogin: (staff: Staff) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { token, staff } = await api.login(email, password);
      session.save(token);
      onLogin(staff);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="login" onSubmit={submit}>
      <h1>Carob console</h1>
      <label>
        Work email
        <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label>
        Password
        <input
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      {error ? <p role="alert" className="error">{error}</p> : null}
      <button type="submit" disabled={busy}>{busy ? "Signing in" : "Sign in"}</button>
    </form>
  );
}
