import { useBackendHealth } from "../hooks/useBackendHealth";
import { ConnectionStatus } from "../components/ConnectionStatus";
import { useAuth } from "../context/AuthContext";
import { beginGoogleSignIn } from "../services/auth";
import { ConversationWorkspace } from "./ConversationWorkspace";
import { useEffect, useState } from "react";

export function HomePage() {
  const health = useBackendHealth();
  const auth = useAuth();
  const [loginError, setLoginError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("auth_error")) {
      setLoginError("No se pudo completar el acceso con Google. Inténtalo de nuevo.");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  async function handleLogout() {
    try {
      await auth.logout();
      setLoginError(null);
    } catch {
      setLoginError("La sesión se cerró en este dispositivo, pero no se pudo confirmar la revocación remota.");
    }
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="SecureAssist AI, inicio">
          <span className="brand-mark" aria-hidden="true">S</span>
          <span>SecureAssist <strong>AI</strong></span>
        </a>
        <span className="topbar-label">ASISTENCIA TÉCNICA</span>
      </header>

      {auth.state === "authenticated" && auth.accessToken ? <ConversationWorkspace accessToken={auth.accessToken} /> : <section className="hero" aria-labelledby="page-title">
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-dot" /> ESTADO DEL SISTEMA</p>
          <h1 id="page-title">Tu soporte técnico,<br /><span>siempre a mano.</span></h1>
          <p className="intro">
            Estamos preparando una herramienta para ayudarte a resolver problemas
            de cámaras, grabadores y sistemas de seguridad.
          </p>

          <ConnectionStatus health={health} onRetry={() => void health.retry()} />
          <section className="auth-card" aria-live="polite">
            {auth.state === "loading" && <p className="auth-message">Comprobando tu sesión…</p>}
            {auth.state === "unavailable" && (
              <div className="auth-copy"><strong>Acceso no disponible</strong><span>{auth.error}</span>
                <button className="auth-secondary" type="button" onClick={() => void auth.refresh()}>Reintentar</button>
              </div>
            )}
            {auth.state === "anonymous" && (
              <div className="auth-copy">
                <strong>Acceso para instaladores</strong>
                <span>Inicia sesión de forma segura con tu cuenta de Google.</span>
                {loginError && <span className="auth-error" role="alert">{loginError}</span>}
                <button className="google-button" type="button" onClick={() => {
                  try { beginGoogleSignIn(); }
                  catch (error) { setLoginError(error instanceof Error ? error.message : "No se pudo iniciar el acceso."); }
                }}>Continuar con Google</button>
              </div>
            )}
            {auth.state === "authenticated" && auth.user && (
              <div className="auth-copy">
                <strong>Sesión iniciada</strong>
                <span>{auth.user.name || auth.user.email}</span>
                {auth.user.name && <span className="auth-subtle">{auth.user.email}</span>}
                {loginError && <span className="auth-error" role="alert">{loginError}</span>}
                <button className="auth-secondary" type="button" onClick={() => void handleLogout()}>Cerrar sesión</button>
              </div>
            )}
          </section>
        </div>

        <aside className="visual-panel" aria-label="Áreas de asistencia">
          <div className="visual-glow" />
          <div className="camera-graphic" aria-hidden="true">
            <div className="camera-body"><span className="camera-lens" /></div>
            <div className="camera-mount" />
            <div className="signal signal--one" />
            <div className="signal signal--two" />
          </div>
          <div className="panel-caption">
            <span className="panel-caption-line" />
            <span>HECHO PARA INSTALADORES</span>
          </div>
          <div className="panel-footer">
            <span>01</span><span className="panel-footer-rule" /><span>DIAGNÓSTICO TÉCNICO</span>
          </div>
        </aside>
      </section>}

      <footer className="footer">
        <span>SECUREASSIST AI <span className="footer-separator">/</span> MVP</span>
        <span>Una herramienta en desarrollo para el trabajo en campo.</span>
      </footer>
    </main>
  );
}
