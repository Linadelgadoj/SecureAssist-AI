import { useCallback, useEffect, useRef, useState } from "react";

import {
  ConversationApiError,
  createConversation,
  listConversations,
  listMessages,
  requestReply,
  sendMessage,
} from "../services/conversations";
import { MessageText } from "../components/MessageText";
import type { Conversation, ConversationMessage } from "../types/conversations";

function formatActivity(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "short" }).format(date);
}

export function ConversationWorkspace({ accessToken }: { accessToken: string }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [historyCursor, setHistoryCursor] = useState<string | null>(null);
  const [messageCursor, setMessageCursor] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingMoreHistory, setLoadingMoreHistory] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [loadingMoreMessages, setLoadingMoreMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [replying, setReplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const page = await listConversations(accessToken);
      setConversations(page.items);
      setHistoryCursor(page.next_cursor);
      setActiveId((current) => current && page.items.some((item) => item.id === current) ? current : page.items[0]?.id ?? null);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo cargar el historial.");
    } finally {
      setLoadingHistory(false);
    }
  }, [accessToken]);

  useEffect(() => { void loadHistory(); }, [loadHistory]);

  async function loadMoreHistory() {
    if (!historyCursor || loadingMoreHistory) return;
    setLoadingMoreHistory(true);
    try {
      const page = await listConversations(accessToken, historyCursor);
      setConversations((items) => [...items, ...page.items.filter((item) => !items.some((existing) => existing.id === item.id))]);
      setHistoryCursor(page.next_cursor);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo ampliar el historial.");
    } finally { setLoadingMoreHistory(false); }
  }

  useEffect(() => {
    if (!activeId) { setMessages([]); setMessageCursor(null); return; }
    let active = true;
    setMessages([]);
    setMessageCursor(null);
    setLoadingMessages(true);
    void listMessages(accessToken, activeId)
      .then((page) => { if (active) { setMessages(page.items); setMessageCursor(page.next_cursor); setError(null); } })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "No se pudieron cargar los mensajes."); })
      .finally(() => { if (active) setLoadingMessages(false); });
    return () => { active = false; };
  }, [accessToken, activeId]);

  async function loadMoreMessages() {
    if (!activeId || !messageCursor || loadingMoreMessages) return;
    setLoadingMoreMessages(true);
    try {
      const page = await listMessages(accessToken, activeId, messageCursor);
      setMessages((items) => [...items, ...page.items]);
      setMessageCursor(page.next_cursor);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudieron cargar más mensajes.");
    } finally { setLoadingMoreMessages(false); }
  }

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages]);

  async function startConversation() {
    setError(null);
    try {
      const conversation = await createConversation(accessToken);
      setConversations((items) => [conversation, ...items]);
      setActiveId(conversation.id);
      setHistoryOpen(false);
      setDraft("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo iniciar una conversación.");
    }
  }

  function touchConversation(conversationId: string, at: string) {
    setConversations((items) => items
      .map((item) => item.id === conversationId ? { ...item, last_activity_at: at } : item)
      .sort((a, b) => Date.parse(b.last_activity_at) - Date.parse(a.last_activity_at)));
  }

  async function askAssistant(conversationId: string) {
    setReplying(true);
    setError(null);
    try {
      const reply = await requestReply(accessToken, conversationId);
      setMessages((items) => [...items, reply]);
      touchConversation(conversationId, reply.created_at);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "El asistente no pudo responder.");
    } finally {
      setReplying(false);
    }
  }

  async function handleSend() {
    const content = draft.trim();
    if (!content || sending || replying) return;
    setSending(true);
    setError(null);
    let createdConversation: Conversation | null = null;
    try {
      let conversationId = activeId;
      if (!conversationId) {
        createdConversation = await createConversation(accessToken);
        conversationId = createdConversation.id;
        setConversations((items) => [createdConversation!, ...items]);
      }
      const message = await sendMessage(accessToken, conversationId, content);
      setMessages((items) => [...items, message]);
      if (createdConversation) setActiveId(createdConversation.id);
      setDraft("");
      touchConversation(conversationId, message.created_at);
      setSending(false);
      await askAssistant(conversationId);
    } catch (reason) {
      if (createdConversation) setActiveId(createdConversation.id);
      setError(reason instanceof ConversationApiError
        ? reason.message
        : "No se pudo guardar el mensaje. El texto permanece en el campo para que puedas reintentar.");
    } finally {
      setSending(false);
    }
  }

  function handleComposerKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  }

  const activeConversation = conversations.find((item) => item.id === activeId) ?? null;
  // Último mensaje sin respuesta (el asistente falló o no estaba disponible): se ofrece reintentar.
  const awaitingReply = !!activeId && !replying && !sending && !loadingMessages && !messageCursor
    && messages.length > 0 && messages[messages.length - 1].role === "installer";

  return (
    <section className="conversation-workspace" aria-label="Conversaciones de asistencia técnica">
      <aside className={`conversation-sidebar${historyOpen ? " conversation-sidebar--open" : ""}`}>
        <div className="sidebar-heading">
          <div>
            <span className="workspace-eyebrow">ESPACIO PRIVADO</span>
            <h1>Conversaciones</h1>
          </div>
          <button className="icon-button sidebar-close" type="button" aria-label="Cerrar historial" onClick={() => setHistoryOpen(false)}>×</button>
        </div>
        <button className="new-conversation-button" type="button" onClick={() => void startConversation()}>
          <span aria-hidden="true">＋</span> Nueva conversación
        </button>
        <div className="history-label">TU HISTORIAL <span>{conversations.length.toString().padStart(2, "0")}</span></div>
        <nav className="conversation-list" aria-label="Historial de conversaciones">
          {loadingHistory && <p className="sidebar-hint">Cargando tu historial…</p>}
          {!loadingHistory && conversations.length === 0 && <p className="sidebar-hint">Tus conversaciones aparecerán aquí.</p>}
          {conversations.map((conversation) => (
            <button
              className={`conversation-item${activeId === conversation.id ? " conversation-item--active" : ""}`}
              key={conversation.id}
              type="button"
              onClick={() => { setActiveId(conversation.id); setHistoryOpen(false); setError(null); }}
            >
              <span className="conversation-item-mark" aria-hidden="true">◌</span>
              <span className="conversation-item-copy"><strong>{conversation.title}</strong><small>{formatActivity(conversation.last_activity_at)}</small></span>
            </button>
          ))}
          {historyCursor && <button className="load-more-button" type="button" disabled={loadingMoreHistory} onClick={() => void loadMoreHistory()}>
            {loadingMoreHistory ? "Cargando…" : "Cargar más conversaciones"}
          </button>}
        </nav>
        <div className="sidebar-privacy"><span aria-hidden="true">◈</span><span>Tu historial es privado y solo tú puedes consultarlo.</span></div>
      </aside>

      <div className="conversation-main">
        <div className="conversation-topline">
          <button className="icon-button history-toggle" type="button" aria-label="Abrir historial" onClick={() => setHistoryOpen(true)}>☰</button>
          <div className="active-conversation-heading">
            <span className="conversation-status-dot" />
            <div><strong>{activeConversation?.title ?? "Asistencia técnica"}</strong><small>Historial privado</small></div>
          </div>
          <span className="topline-code">SA / CHAT</span>
        </div>

        <div className="message-stream" aria-live="polite" aria-busy={loadingMessages || sending}>
          {!activeConversation && !loadingHistory && (
            <div className="chat-welcome">
              <span className="welcome-mark" aria-hidden="true">S</span>
              <p className="workspace-eyebrow">ASISTENCIA PARA INSTALADORES</p>
              <h2>¿Qué necesitas revisar?</h2>
              <p>Describe la falla y SecureAssist te ayuda a diagnosticarla y a revisar si hay repuestos en el inventario.</p>
            </div>
          )}
          {activeConversation && messages.length === 0 && !loadingMessages && (
            <div className="empty-conversation">
              <span className="empty-line" />
              <p>Empieza por describir lo que observas en la instalación.</p>
              <small>Los mensajes se guardarán en tu historial privado.</small>
            </div>
          )}
          {loadingMessages && <p className="stream-loading"><span className="loading-pulse" /> Cargando mensajes…</p>}
          {messageCursor && <button className="load-more-button load-more-messages" type="button" disabled={loadingMoreMessages} onClick={() => void loadMoreMessages()}>
            {loadingMoreMessages ? "Cargando…" : "Cargar mensajes más recientes"}
          </button>}
          {messages.map((message) => {
            const fromAssistant = message.role === "assistant";
            return (
              <article className={`message-row${fromAssistant ? " message-row--assistant" : ""}`} key={message.id}>
                <div className="message-avatar" aria-hidden="true">{fromAssistant ? "SA" : "TÚ"}</div>
                <div className="message-bubble-wrap"><div className="message-meta"><strong>{fromAssistant ? "SecureAssist" : "Tú"}</strong><time dateTime={message.created_at}>{new Intl.DateTimeFormat("es-CO", { hour: "2-digit", minute: "2-digit" }).format(new Date(message.created_at))}</time></div>
                  {fromAssistant
                    ? <div className="message-bubble message-bubble--assistant"><MessageText text={message.content_text} /></div>
                    : <p className="message-bubble">{message.content_text}</p>}
                </div>
              </article>
            );
          })}
          {sending && <p className="stream-loading"><span className="loading-pulse" /> Guardando mensaje…</p>}
          {replying && <p className="stream-loading"><span className="loading-pulse" /> SecureAssist está revisando tu caso…</p>}
          {awaitingReply && (
            <button className="load-more-button load-more-messages" type="button" onClick={() => void askAssistant(activeId!)}>
              Pedir respuesta al asistente
            </button>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="composer-area">
          {error && <div className="conversation-error" role="alert"><span aria-hidden="true">!</span><span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="Cerrar mensaje de error">×</button></div>}
          <div className="composer-box">
            <textarea
              aria-label="Escribe un mensaje"
              placeholder="Describe lo que ocurre con el equipo…"
              value={draft}
              maxLength={8000}
              rows={2}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              disabled={sending || replying}
            />
            <div className="composer-controls"><span>Enter para enviar <i>·</i> Shift + Enter para nueva línea</span>
              <button className="send-button" type="button" onClick={() => void handleSend()} disabled={!draft.trim() || sending || replying} aria-label="Enviar mensaje">
                {sending ? <span className="button-spinner" /> : <span aria-hidden="true">↑</span>}
              </button>
            </div>
          </div>
          <p className="composer-note">Los mensajes se guardan de forma privada. El asistente puede equivocarse: verifica antes de intervenir un equipo. No incluyas contraseñas ni tokens.</p>
        </div>
      </div>
    </section>
  );
}
