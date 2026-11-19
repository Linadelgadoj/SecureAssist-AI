import type {
  Account,
  ClientDetail,
  ClientInput,
  ClientSummary,
  EquipmentDetail,
  EquipmentInput,
  EquipmentStatus,
  LocationKind,
  ManualMovementReason,
  Product,
  ProductInput,
  RepairDetail,
  RepairStatus,
  RepairSummary,
  Role,
  StockLocation,
  StockMovement,
} from "../types/inventory";

const configuredApiBase = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, "");
const API_BASE_URL = configuredApiBase?.endsWith("/api/v1")
  ? configuredApiBase
  : configuredApiBase
    ? `${configuredApiBase}/api/v1`
    : undefined;

/** Error de la API con el código de negocio del backend (p. ej. INSUFFICIENT_STOCK). */
export class InventoryApiError extends Error {
  constructor(message: string, readonly status?: number, readonly code?: string) {
    super(message);
    this.name = "InventoryApiError";
  }
}

const FALLBACK_BY_STATUS: Record<number, string> = {
  403: "Tu rol no permite esta acción.",
  404: "No se encontró el registro.",
  422: "Revisa los datos del formulario.",
  503: "El inventario no está disponible. Comprueba que la base de datos esté iniciada.",
};

type Query = Record<string, string | number | boolean | null | undefined>;

function buildQuery(query?: Query): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "" && value !== false) params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

async function request<T>(path: string, token: string, init: RequestInit = {}, query?: Query): Promise<T> {
  if (!API_BASE_URL) throw new InventoryApiError("Falta configurar la URL del backend.");
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}${buildQuery(query)}`, {
      ...init,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        ...(init.body ? { "Content-Type": "application/json" } : {}),
      },
      signal: init.signal ?? AbortSignal.timeout(10000),
    });
  } catch {
    throw new InventoryApiError("No fue posible conectar con el backend.");
  }
  if (!response.ok) {
    let message = FALLBACK_BY_STATUS[response.status] ?? "No fue posible completar la operación.";
    let code: string | undefined;
    try {
      const body = await response.json() as { error?: { message?: string; code?: string } };
      code = body.error?.code;
      // Los 409 traen un mensaje de negocio pensado para el usuario; el resto se resume.
      if (response.status === 409 && typeof body.error?.message === "string") message = body.error.message;
    } catch { /* Se usa el mensaje genérico. */ }
    throw new InventoryApiError(message, response.status, code);
  }
  return response.json() as Promise<T>;
}

const send = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

// ------------------------------------------------------------------ cuenta y usuarios
export const getMe = (token: string) => request<Account>("/me", token);
export const listUsers = (token: string) => request<Account[]>("/users", token);
export const updateUser = (token: string, id: string, change: { role?: Role; is_active?: boolean }) =>
  request<Account>(`/users/${encodeURIComponent(id)}`, token, send("PATCH", change));

// ------------------------------------------------------------------ catálogo y stock
export const listProducts = (token: string, filters: { q?: string; category?: string; low_stock?: boolean; include_inactive?: boolean } = {}) =>
  request<Product[]>("/products", token, {}, filters);
export const getProduct = (token: string, id: string) => request<Product>(`/products/${encodeURIComponent(id)}`, token);
export const createProduct = (token: string, input: ProductInput) => request<Product>("/products", token, send("POST", input));
export const updateProduct = (token: string, id: string, change: Partial<ProductInput> & { is_active?: boolean }) =>
  request<Product>(`/products/${encodeURIComponent(id)}`, token, send("PATCH", change));

export const listLocations = (token: string) => request<StockLocation[]>("/locations", token);
export const createLocation = (token: string, input: { name: string; kind: LocationKind }) =>
  request<StockLocation>("/locations", token, send("POST", input));

export const listMovements = (token: string, productId?: string, limit = 30) =>
  request<StockMovement[]>("/stock/movements", token, {}, { product_id: productId, limit });
export const registerMovement = (token: string, input: {
  product_id: string; location_id: string; reason: ManualMovementReason; quantity: number; note?: string | null;
}) => request<StockMovement>("/stock/movements", token, send("POST", input));
export const transferStock = (token: string, input: {
  product_id: string; from_location_id: string; to_location_id: string; quantity: number; note?: string | null;
}) => request<StockMovement[]>("/stock/transfers", token, send("POST", input));

// ------------------------------------------------------------------ clientes y equipos
export const listClients = (token: string, q?: string) => request<ClientSummary[]>("/clients", token, {}, { q, limit: 100 });
export const getClient = (token: string, id: string) => request<ClientDetail>(`/clients/${encodeURIComponent(id)}`, token);
export const createClient = (token: string, input: ClientInput) => request<ClientDetail>("/clients", token, send("POST", input));
export const addEquipment = (token: string, clientId: string, input: EquipmentInput) =>
  request<EquipmentDetail>(`/clients/${encodeURIComponent(clientId)}/equipment`, token, send("POST", input));
export const getEquipment = (token: string, id: string) => request<EquipmentDetail>(`/equipment/${encodeURIComponent(id)}`, token);
export const updateEquipmentStatus = (token: string, id: string, status: EquipmentStatus) =>
  request<EquipmentDetail>(`/equipment/${encodeURIComponent(id)}`, token, send("PATCH", { status }));

// ------------------------------------------------------------------ reparaciones
export const listRepairs = (token: string, filters: { status?: RepairStatus | ""; mine?: boolean; client_id?: string } = {}) =>
  request<RepairSummary[]>("/repairs", token, {}, filters);
export const getRepair = (token: string, id: string) => request<RepairDetail>(`/repairs/${encodeURIComponent(id)}`, token);
export const openRepair = (token: string, input: { client_id: string; equipment_id?: string | null; problem_description: string }) =>
  request<RepairDetail>("/repairs", token, send("POST", input));
export const updateRepair = (token: string, id: string, change: { diagnosis?: string | null; solution?: string | null; status?: RepairStatus }) =>
  request<RepairDetail>(`/repairs/${encodeURIComponent(id)}`, token, send("PATCH", change));
export const addRepairPart = (token: string, id: string, input: { product_id: string; location_id: string; quantity: number; note?: string | null }) =>
  request<StockMovement>(`/repairs/${encodeURIComponent(id)}/parts`, token, send("POST", input));
