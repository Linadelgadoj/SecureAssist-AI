export interface Conversation {
  id: string;
  title: string;
  state: "open";
  created_at: string;
  last_activity_at: string;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: "installer";
  content_text: string;
  processing_state: "received";
  created_at: string;
}

export interface ConversationList {
  items: Conversation[];
  next_cursor: string | null;
}

export interface MessageList {
  items: ConversationMessage[];
  next_cursor: string | null;
}
