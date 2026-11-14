import type { Conversation, ConversationList, ConversationMessage, MessageList } from "../types/conversations";

const configuredApiBase = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, "");
const API_BASE_URL = configuredApiBase?.endsWith("/api/v1")
  ? configuredApiBase
  : configuredApiBase
    ? `${configuredApiBase}/api/v1`
    : undefined;

export class ConversationApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ConversationApiError";
  }
}

async function request<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  if (!API_BASE_URL) throw new ConversationApiError("Falta configurar la URL del backend.");
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
      signal: init.signal ?? AbortSignal.timeout(10000),
    });
  } catch {
    throw new ConversationApiError("No fue posible conectar con el servicio de conversaciones.");
  }

  if (!response.ok) {
    let message = response.status === 503
      ? "El almacenamiento de conversaciones no está disponible. Comprueba la configuración de Supabase."
      : "No fue posible completar la operación. Inténtalo de nuevo.";
    try {
      const body = await response.json() as { error?: { message?: string } };
      if (typeof body.error?.message === "string") message = body.error.message;
    } catch { /* Use the safe fallback message. */ }
    throw new ConversationApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export async function listConversations(token: string, cursor?: string | null): Promise<ConversationList> {
  const query = cursor ? `?limit=20&cursor=${encodeURIComponent(cursor)}` : "?limit=20";
  return request<ConversationList>(`/conversations${query}`, token);
}

export function createConversation(token: string): Promise<Conversation> {
  return request<Conversation>("/conversations", token, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function listMessages(token: string, conversationId: string, cursor?: string | null): Promise<MessageList> {
  const query = cursor ? `?limit=100&cursor=${encodeURIComponent(cursor)}` : "?limit=100";
  return request<MessageList>(`/conversations/${encodeURIComponent(conversationId)}/messages${query}`, token);
}

export function sendMessage(token: string, conversationId: string, contentText: string): Promise<ConversationMessage> {
  return request<ConversationMessage>(`/conversations/${encodeURIComponent(conversationId)}/messages`, token, {
    method: "POST",
    body: JSON.stringify({ content_text: contentText }),
  });
}
