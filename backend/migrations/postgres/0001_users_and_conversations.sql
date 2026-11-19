-- Usuarios de la aplicación, roles e historial de conversaciones.
-- El id del usuario es el `sub` que entrega el proveedor de identidad
-- (Supabase Auth o el login de prueba), así que no se generan ids propios.

CREATE TABLE app_users (
    id          uuid PRIMARY KEY,
    email       text NOT NULL UNIQUE CHECK (char_length(email) BETWEEN 3 AND 320),
    full_name   text CHECK (char_length(full_name) <= 200),
    role        text NOT NULL DEFAULT 'technician' CHECK (role IN ('admin', 'technician')),
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE conversations (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id    uuid NOT NULL REFERENCES app_users (id) ON DELETE CASCADE,
    title            text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 120),
    state            text NOT NULL DEFAULT 'open' CHECK (state = 'open'),
    created_at       timestamptz NOT NULL DEFAULT now(),
    last_activity_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, owner_user_id)
);

CREATE INDEX conversations_owner_activity_idx
    ON conversations (owner_user_id, last_activity_at DESC, id DESC);

CREATE TABLE messages (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  uuid NOT NULL,
    owner_user_id    uuid NOT NULL,
    -- 'assistant' queda permitido desde ya para las respuestas del chatbot (fase 4).
    role             text NOT NULL DEFAULT 'installer' CHECK (role IN ('installer', 'assistant')),
    content_text     text NOT NULL CHECK (char_length(content_text) BETWEEN 1 AND 8000),
    processing_state text NOT NULL DEFAULT 'received' CHECK (processing_state IN ('received', 'completed', 'failed')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    -- La conversación debe pertenecer al mismo propietario que el mensaje.
    FOREIGN KEY (conversation_id, owner_user_id)
        REFERENCES conversations (id, owner_user_id) ON DELETE CASCADE
);

CREATE INDEX messages_owner_conversation_order_idx
    ON messages (owner_user_id, conversation_id, created_at, id);
