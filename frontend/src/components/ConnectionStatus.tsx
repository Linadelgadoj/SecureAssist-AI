import type { HealthState } from "../hooks/useBackendHealth";

interface ConnectionStatusProps {
  health: HealthState;
  onRetry: () => void;
}

export function ConnectionStatus({ health, onRetry }: ConnectionStatusProps) {
  return (
    <div className={`connection-card connection-card--${health.status}`} role="status" aria-live="polite">
      <span className="connection-indicator" aria-hidden="true" />
      <div className="connection-copy">
        <strong>
          {health.status === "checking" && "Comprobando conexión"}
          {health.status === "connected" && "Backend conectado"}
          {health.status === "unavailable" && "Backend no disponible"}
        </strong>
        <span>
          {health.status === "checking" && "Contactando el servicio local…"}
          {health.status === "connected" && `Conexión activa · solicitud ${health.result.request_id}`}
          {health.status === "unavailable" && health.error}
        </span>
      </div>
      {health.status === "unavailable" && (
        <button className="retry-button" type="button" onClick={onRetry}>
          Reintentar
        </button>
      )}
    </div>
  );
}
