-- Supabase: permite guardar las respuestas del asistente en el historial.
-- (El modo PostgreSQL local ya lo incluye en migrations/postgres/0001.)
--
-- Nota de seguridad: el backend inserta con el JWT del propio instalador (RLS),
-- así que ese usuario podría insertar por PostgREST un mensaje 'assistant' en SU
-- conversación privada. Solo se afecta a sí mismo; si se quiere impedir, mover la
-- inserción de respuestas a una función SECURITY DEFINER llamada por el backend.

alter table public.messages drop constraint if exists messages_role_check;
alter table public.messages add constraint messages_role_check
    check (role in ('installer', 'assistant'));

alter table public.messages drop constraint if exists messages_processing_state_check;
alter table public.messages add constraint messages_processing_state_check
    check (processing_state in ('received', 'completed', 'failed'));
