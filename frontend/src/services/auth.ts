import type { AuthSession } from "../types/auth";

const configuredApiBase = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, "");
const API_BASE_URL = configuredApiBase?.endsWith("/api/v1")
  ? configuredApiBase
  : configuredApiBase
    ? `${configuredApiBase}/api/v1`
    : undefined;

export class AuthApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "AuthApiError";
  }
}

let sessionRequest: Promise<AuthSession> | null = null;

function apiUrl(path: string): string {
  if (!API_BASE_URL) throw new AuthApiError("No está configurada la URL del backend.");
  return `${API_BASE_URL}${path}`;
}

async function readSession(response: Response): Promise<AuthSession> {
  if (!response.ok) {
    const message = response.status === 503
      ? "El servicio de acceso no está disponible temporalmente. Intenta más tarde."
      : response.status === 401
        ? "La sesión venció. Inicia sesión nuevamente."
        : "No fue posible consultar tu sesión.";
    throw new AuthApiError(message, response.status);
  }
  return response.json() as Promise<AuthSession>;
}

export function beginGoogleSignIn(): void {
  window.location.assign(apiUrl("/auth/google/start"));
}

export function getSession(): Promise<AuthSession> {
  if (!sessionRequest) {
    sessionRequest = (async () => {
      try {
        return await readSession(await fetch(apiUrl("/auth/session"), {
          method: "GET", credentials: "include", headers: { Accept: "application/json" },
        }));
      } catch (error) {
        if (error instanceof AuthApiError) throw error;
        throw new AuthApiError("No fue posible contactar el servicio de acceso.");
      }
    })().finally(() => { sessionRequest = null; });
  }
  return sessionRequest;
}

export async function refreshSession(): Promise<AuthSession> {
  try {
    return await readSession(await fetch(apiUrl("/auth/refresh"), {
      method: "POST", credentials: "include", headers: { Accept: "application/json" },
    }));
  } catch (error) {
    if (error instanceof AuthApiError) throw error;
    throw new AuthApiError("No fue posible renovar la sesión.");
  }
}

export async function endSession(): Promise<void> {
  try {
    const response = await fetch(apiUrl("/auth/logout"), {
      method: "POST", credentials: "include", headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new AuthApiError("No fue posible cerrar la sesión.", response.status);
  } catch (error) {
    if (error instanceof AuthApiError) throw error;
    throw new AuthApiError("No fue posible contactar el servicio de acceso.");
  }
}
