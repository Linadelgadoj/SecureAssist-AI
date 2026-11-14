import type { HealthResponse } from "../types/health";

const configuredApiBase = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, "");
const API_PREFIX = "/api/v1";
const API_BASE_URL = configuredApiBase
  ? configuredApiBase.endsWith(API_PREFIX)
    ? configuredApiBase
    : `${configuredApiBase}${API_PREFIX}`
  : undefined;

export class ApiConnectionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiConnectionError";
  }
}

export async function getHealth(): Promise<HealthResponse> {
  if (!API_BASE_URL) {
    throw new ApiConnectionError(
      "Falta configurar VITE_API_BASE_URL para consultar el backend.",
    );
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    throw new ApiConnectionError(
      "No fue posible conectar con el backend. Comprueba que esté iniciado.",
    );
  }

  if (!response.ok) {
    throw new ApiConnectionError(
      `El backend respondió con el estado HTTP ${response.status}.`,
    );
  }

  const body: unknown = await response.json();
  if (
    typeof body !== "object" ||
    body === null ||
    !("status" in body) ||
    body.status !== "ok" ||
    !("request_id" in body) ||
    typeof body.request_id !== "string"
  ) {
    throw new ApiConnectionError("El backend devolvió una respuesta no válida.");
  }

  return body as HealthResponse;
}
