import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import type { EquipmentStatus, LocationKind, RepairStatus, Role } from "../types/inventory";

export const ROLE_LABEL: Record<Role, string> = { admin: "Administrador", technician: "Técnico" };
export const LOCATION_KIND_LABEL: Record<LocationKind, string> = { warehouse: "Bodega", vehicle: "Vehículo", other: "Otra" };
export const EQUIPMENT_STATUS_LABEL: Record<EquipmentStatus, string> = {
  operational: "Operativo", in_repair: "En reparación", out_of_service: "Fuera de servicio", removed: "Retirado",
};
export const REPAIR_STATUS_LABEL: Record<RepairStatus, string> = {
  open: "Abierta", in_progress: "En progreso", resolved: "Resuelta", cancelled: "Cancelada",
};
export const MOVEMENT_REASON_LABEL: Record<string, string> = {
  receipt: "Entrada", issue: "Salida", adjustment: "Ajuste", repair: "Reparación",
  transfer_in: "Traslado (entra)", transfer_out: "Traslado (sale)",
};

const TONE: Record<string, "ok" | "warn" | "bad" | "muted"> = {
  operational: "ok", resolved: "ok", in_repair: "warn", in_progress: "warn", open: "warn",
  out_of_service: "bad", removed: "muted", cancelled: "muted",
};

export function StatusBadge({ status, label }: { status: string; label: string }) {
  return <span className={`badge badge--${TONE[status] ?? "muted"}`}>{label}</span>;
}

export function Notice({ kind, children, onClose }: { kind: "error" | "success"; children: ReactNode; onClose?: () => void }) {
  return (
    <div className={`notice notice--${kind}`} role={kind === "error" ? "alert" : "status"}>
      <span>{children}</span>
      {onClose && <button type="button" onClick={onClose} aria-label="Cerrar aviso">×</button>}
    </div>
  );
}

export function Field({ label, children, wide }: { label: string; children: ReactNode; wide?: boolean }) {
  return <label className={`field${wide ? " field--wide" : ""}`}><span>{label}</span>{children}</label>;
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="empty-state">{children}</p>;
}

export function formatDate(value: string | null, withTime = false): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("es-CO", withTime
    ? { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }
    : { day: "numeric", month: "short", year: "numeric" }).format(date);
}

export function errorMessage(reason: unknown, fallback: string): string {
  return reason instanceof Error && reason.message ? reason.message : fallback;
}

/** Carga datos con un loader y permite recargar. Ignora respuestas de cargas anteriores. */
export function useLoader<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const load = useCallback(loader, deps);

  const reload = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true);
    try {
      const result = await load();
      if (current === generation.current) { setData(result); setError(null); }
    } catch (reason) {
      if (current === generation.current) setError(errorMessage(reason, "No se pudieron cargar los datos."));
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, [load]);

  useEffect(() => { void reload(); }, [reload]);
  return { data, loading, error, reload, setError };
}

/** Ejecuta una acción de formulario con estado de envío, error y aviso de éxito. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const run = useCallback(async (action: () => Promise<unknown>, successText?: string): Promise<boolean> => {
    setBusy(true); setError(null); setSuccess(null);
    try {
      await action();
      if (successText) setSuccess(successText);
      return true;
    } catch (reason) {
      setError(errorMessage(reason, "No fue posible completar la operación."));
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  return { busy, error, success, run, setError, setSuccess };
}

/** Convierte "" en null para campos opcionales del formulario. */
export function optional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}
