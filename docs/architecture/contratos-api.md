# SecureAssist AI — Contratos de API del MVP

**Estado:** especificación propuesta para revisión; no constituye código ni selección de decisiones que las fuentes mantienen pendientes.  
**Versión:** 1.0  
**Fuentes:** `AGENTS.md`, `docs/architecture/arquitectura-tecnica.md`, `docs/architecture/comportamiento-chatbot.md`, `docs/requirements/requisitos-funcionales-mvp.md` y `docs/architecture/modelo-datos.md`.

## 1. Propósito y límites

Este documento define la interfaz REST entre React + TypeScript y el backend FastAPI del monolito modular SecureAssist AI. FastAPI valida identidad y propiedad, ejecuta reglas de negocio, accede a PostgreSQL/Supabase y Storage privado y, cuando corresponda, llama al proveedor multimodal aprobado. El frontend no llama a OpenAI ni accede a credenciales privilegiadas.

No se crean aquí endpoints de inventario, roles administrativos, servicios separados, tablas, migraciones ni mecanismos de transporte no aprobados. Los nombres de ruta, esquemas y flujos marcados como propuesta deberán revisarse antes de convertirse en un contrato congelado. Las operaciones del proveedor de identidad se distinguen de las rutas propias de FastAPI.

> **Actualización 2026-11-19:** se agregaron las rutas de inventario, de roles (`/me`, `/users`) y `POST /conversations/{id}/reply` para el asistente; se documentan aparte. Las rutas de este documento no cambian. Ver [inventario-y-asistente.md](inventario-y-asistente.md).

## 2. Convenciones comunes

### 2.1 Transporte, URL y representación

- URL lógica: `https://<dominio-api-aprobado>/api/v1`. El dominio, hosting y configuración por ambiente siguen pendientes; el marcador no es una URL operativa.
- Producción debe usar HTTPS. No se define una URL HTTP de producción.
- Solicitudes y respuestas ordinarias usan `application/json; charset=utf-8`. Carga de fotografía usa `multipart/form-data`; descarga controlada devuelve el MIME real del objeto.
- JSON usa `snake_case`; los nombres de recursos y rutas son plurales y en minúscula. El frontend traduce a sus convenciones internas si lo requiere.
- Los identificadores de recursos propios son UUID en formato canónico. El identificador del usuario procede del `sub` UUID del JWT de Supabase Auth, nunca de un `owner_user_id` provisto por el cliente.
- Las fechas y horas usan ISO 8601 con zona explícita, preferiblemente UTC, por ejemplo `2026-11-14T14:30:00Z`.
- Los cuerpos JSON rechazan propiedades desconocidas en operaciones sensibles. Texto se valida por tipo y límites aprobados en implementación; las respuestas omiten valores nulos cuando el esquema indique `null` explícitamente.

### 2.2 Autenticación de las rutas FastAPI

Las rutas privadas requieren `Authorization: Bearer <access_token>`. FastAPI valida la firma y las claims necesarias del JWT con el mecanismo Supabase aprobado, comprueba emisor, audiencia, expiración y sujeto, y deriva la identidad únicamente de `sub`. No acepta identidad o propietario del body/query como sustituto del token.

La validación JWT exacta, selección de claves/rotación y configuración de Auth están pendientes de aprobación/configuración. Si no se puede verificar el token contra la configuración esperada, el backend falla cerrado. Los tokens de refresco se manejan mediante el proveedor de identidad; nunca se registran ni se devuelven desde una ruta propia.

### 2.3 Paginación, filtros y orden

Para colecciones se propone paginación por cursor: `limit` (valor inicial recomendado 20, máximo recomendado 100) y `cursor` opaco devuelto por la respuesta. Los valores límite son propuesta de API y deben aprobarse antes de implementación. Respuesta común: `{ "items": [], "next_cursor": null }`. No se acepta `owner_user_id` como filtro. El orden es fijo y documentado por recurso: conversaciones por `last_activity_at DESC`, mensajes por `created_at ASC, id ASC`, eventos/resultados por fecha ascendente o descendente según historial; no se admiten campos de orden dinámicos arbitrarios.

Los filtros permitidos se documentan por endpoint. Los cursores deben ser opacos, validados por FastAPI y no revelar datos de otros propietarios.

### 2.4 Concurrencia e idempotencia

Para creación de mensajes, resultados y decisiones de consentimiento, el cliente envía `Idempotency-Key` (UUID generado por cliente) y el backend evita duplicar la misma operación dentro de su ámbito de usuario/ruta durante la ventana de idempotencia que se apruebe. Un reintento con la misma clave y mismo cuerpo devuelve el resultado original; la misma clave con cuerpo distinto produce `409 IDEMPOTENCY_CONFLICT`. La duración de retención de claves es pendiente.

Los cambios de estado pueden usar `If-Match`/ETag o una versión de recurso si se decide necesario; esta especificación no impone control optimista porque las fuentes no lo fijan.

## 3. Formato uniforme de errores

Toda respuesta de error JSON usa esta forma (salvo errores previos del proxy/red que no alcancen FastAPI):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Revisa los datos enviados.",
    "details": [{"field": "content_text", "reason": "required_or_attachment"}],
    "request_id": "a47a8740-c929-42f2-bd04-e7611164ab16"
  }
}
```

`details` puede ser una lista vacía o estar omitida. Los detalles exponen nombres/códigos de campos y no deben incluir prompt, stack trace, token, clave, ruta privada de Storage ni contenido de otro usuario. `request_id` permite correlación con logs seguros; no es un secreto.

| HTTP | Uso en esta API | Ejemplos de código de aplicación |
|---|---|---|
| 400 | Sintaxis/estado de solicitud no aceptable para la operación | `INVALID_REQUEST`, `INVALID_CURSOR` |
| 401 | Token ausente, inválido, revocado o vencido | `AUTH_REQUIRED`, `AUTH_INVALID`, `AUTH_EXPIRED` |
| 403 | Identidad válida sin permiso para una acción | `FORBIDDEN`, `CONSENT_REQUIRED` |
| 404 | Recurso inexistente o no visible para ese usuario | `RESOURCE_NOT_FOUND` |
| 409 | Conflicto de estado, duplicidad o idempotencia | `INVALID_STATE_TRANSITION`, `IDEMPOTENCY_CONFLICT` |
| 413 | Archivo o body excede límite aprobado | `FILE_TOO_LARGE` |
| 415 | Formato de archivo no admitido | `UNSUPPORTED_MEDIA_TYPE` |
| 422 | Campos con estructura/formato no válido | `VALIDATION_ERROR` |
| 429 | Límite de solicitudes aplicado | `RATE_LIMITED` |
| 500 | Error interno no clasificable; respuesta genérica | `INTERNAL_ERROR` |
| 502 | Dependencia externa respondió con error no recuperable | `AI_PROVIDER_ERROR`, `STORAGE_PROVIDER_ERROR` |
| 503 | Dependencia temporalmente indisponible o mantenimiento | `SERVICE_UNAVAILABLE` |
| 504 | Timeout de dependencia/procesamiento sin confirmar resultado final | `UPSTREAM_TIMEOUT` |

Una ruta privada puede devolver `404` para un recurso ajeno en vez de confirmar su existencia con `403`; la política uniforme se debe aplicar a todas las rutas para evitar enumeración.

## 4. Identidad: Supabase Auth y perfil

### 4.1 Operaciones del proveedor de identidad

Registro, inicio/cierre de sesión y recuperación de acceso pertenecen a Supabase Auth, que es la alternativa principal aprobada para evaluación; el método exacto (email/contraseña, enlace, proveedor, políticas de verificación y flujo de refresh) no está aprobado. Por ello esta especificación **no inventa rutas FastAPI** para esos actos ni afirma una ruta concreta del SDK. El frontend usará exclusivamente la integración de cliente que se seleccione; recibirá el access token y lo enviará a FastAPI. Cierre local elimina/revoca la sesión según el flujo de Auth elegido. Recuperación se habilita solo si la configuración final la contempla.

Flujos requeridos, con el límite del contrato actual:

| Operación lógica | Entrada/acción | Resultado visible | Errores que la aplicación debe normalizar | Tratamiento de perfil/API |
|---|---|---|---|---|
| Registro (RF-001) | Datos requeridos por el método de Auth que se apruebe; no se fija si email/contraseña, enlace u otro proveedor | Cuenta Auth creada o indicación de verificación si el proveedor la exige; nunca mostrar token como texto | Datos rechazados, identidad ya registrada, proveedor indisponible, respuesta que requiere verificación | Crear/verificar `INSTALLER_PROFILES` usando identidad autenticada; no permitir API privada hasta token válido y perfil listo. |
| Inicio de sesión (RF-002) | Credenciales/acción correspondientes al método pendiente | Sesión Auth vigente en el almacenamiento aprobado; token se usa como Bearer ante FastAPI | Credenciales inválidas → mensaje genérico y no revela si existe cuenta; cuenta requiere verificación; Auth temporalmente no disponible | En API, token vencido/ inválido responde 401. No se conserva secreto ni se registra. |
| Cierre de sesión (RF-003) | Acción explícita del usuario | Auth intenta revocar/cerrar sesión según método aprobado; UI limpia credenciales locales y deja de consultar rutas privadas | Si no hay conexión, UI bloquea acceso local y muestra que revocación remota no pudo confirmarse; el token podría seguir vigente hasta su expiración según proveedor | No hay ruta FastAPI propuesta; no elimina perfil ni conversaciones. |
| Recuperación de acceso (RF-004) | Solo si la configuración final de Auth la admite | Mensaje neutral de solicitud recibida y flujo del proveedor; nunca confirma si la dirección está registrada | No divulgar existencia de cuenta; proveedor fuera de servicio se comunica sin credenciales | Operación del proveedor, no cambia el perfil/datos técnicos. |

No se puede asignar un `METHOD /path`, body de proveedor o contrato de token de Supabase sin decidir método/configuración. Esa carencia es deliberada: una ruta concreta aquí sería inventar una decisión pendiente. Requisito transversal del usuario para esta API: ninguna clave Supabase ni credencial privilegiada se entrega al frontend; se requiere aprobar cómo se integra Auth sin exponerlas antes de implementar registro/login reales.

FastAPI debe crear o verificar `INSTALLER_PROFILES` de forma confiable al completar el alta Auth. El cliente no puede crear un perfil para otro UUID ni cambiar `account_state` o el identificador Auth.

### 4.2 Endpoints de perfil

#### API-001 — Consultar perfil autenticado

- **Método/ruta:** `GET /api/v1/me`
- **Autenticación/permisos:** Bearer válido; solo perfil cuyo `user_id = sub`.
- **Parámetros:** ninguno.
- **Solicitud:** sin body.
- **Éxito:** `200 OK`.
- **Ejemplo de respuesta:** `{"user_id":"2b31b952-75de-4a01-ae83-73d61cfc54e3","display_name":"Instalador","account_state":"active","created_at":"2026-11-14T14:30:00Z","updated_at":"2026-11-14T14:30:00Z"}`
- **Errores:** `401`, `404 PROFILE_NOT_READY`, `500`.
- **Propiedad:** identidad desde JWT, nunca desde la ruta.
- **Datos:** `INSTALLER_PROFILES`; identidad Auth se consulta/valida según configuración, no se copia contraseña ni secreto.

#### API-002 — Actualizar campos permitidos del perfil

- **Método/ruta:** `PATCH /api/v1/me`
- **Autenticación/permisos:** Bearer válido; editar solo campos permitidos del propio perfil.
- **Body:** JSON con `display_name` opcional (string o `null` según política de borrado). Rechazar `user_id`, `account_state`, roles y propiedades desconocidas.
- **Ejemplo:** `{"display_name":"Lina"}`
- **Éxito:** `200 OK`, devuelve el perfil actualizado con el mismo esquema API-001.
- **Errores:** `400` body vacío, `401`, `404`, `422` longitud/formato inválido, `500`.
- **Propiedad:** el sujeto del JWT fija la fila; RLS/backend verifican que no se altere el propietario.
- **Datos:** `INSTALLER_PROFILES`; campos permitidos limitados a los aprobados.

## 5. Conversaciones e historial

#### API-003 — Crear conversación

- **Método/ruta:** `POST /api/v1/conversations`
- **Autenticación/permisos:** Bearer válido; crear para el usuario autenticado.
- **Body:** `{ "title": "string opcional" }`; omisión genera título neutro/derivado de forma segura. No se requiere problema ni mensaje inicial.
- **Ejemplo:** `{"title":"Cámara del acceso principal"}`
- **Éxito:** `201 Created`, `{"id":"d00c1c11-6100-442f-85f2-634a6b0e77d2","title":"Cámara del acceso principal","state":"open","created_at":"2026-11-14T14:30:00Z","last_activity_at":"2026-11-14T14:30:00Z"}`
- **Errores:** `401`, `422`, `500`.
- **Propiedad:** backend asigna owner desde `sub`; nunca acepta un dueño en el body.
- **Datos:** inserta `CONVERSATIONS`.

#### API-004 — Listar conversaciones propias

- **Método/ruta:** `GET /api/v1/conversations`
- **Autenticación/permisos:** Bearer válido; propietario actual exclusivamente.
- **Query:** `limit`, `cursor`, `state` opcional (`open`, `closed`, `archived`; estados de borrado no son filtros públicos).
- **Ejemplo de solicitud:** `GET /api/v1/conversations?limit=20&state=open`
- **Éxito:** `200 OK`, `{ "items": [{"id":"d00c1c11-6100-442f-85f2-634a6b0e77d2","title":"Cámara del acceso principal","state":"open","created_at":"2026-11-14T14:30:00Z","last_activity_at":"2026-11-14T14:41:00Z"}], "next_cursor": null }`.
- **Errores:** `400 INVALID_CURSOR`, `401`, `422`, `500`.
- **Propiedad:** filtro propietario obligatorio aplicado en backend y RLS.
- **Datos:** lectura `CONVERSATIONS`; no incluye contenido de mensajes.

#### API-005 — Consultar conversación

- **Método/ruta:** `GET /api/v1/conversations/{conversation_id}`
- **Autenticación/permisos:** Bearer válido; dueño del recurso.
- **Parámetros:** `conversation_id` UUID.
- **Body:** ninguno.
- **Éxito:** `200 OK`, objeto conversación de API-003, más `problem_count` entero.
- **Errores:** `400` UUID inválido, `401`, `404` inexistente/no propio, `500`.
- **Propiedad:** comprueba `owner_user_id = sub`; responder 404 para recursos no propios.
- **Datos:** `CONVERSATIONS`, conteo autorizado de `TECHNICAL_ISSUES`.

#### API-006 — Cambiar título o estado de conversación

- **Método/ruta:** `PATCH /api/v1/conversations/{conversation_id}`
- **Autenticación/permisos:** Bearer válido y propietario.
- **Body:** uno o ambos campos permitidos: `title`, `state`. Valores públicos de estado: `open`, `closed`, `archived`; transiciones inválidas se rechazan. `deleted`/`deletion_pending` no se cambian por esta ruta.
- **Ejemplo:** `{"state":"archived"}`
- **Éxito:** `200 OK`, objeto actualizado de API-003.
- **Errores:** `400`, `401`, `404`, `409 INVALID_STATE_TRANSITION`, `422`, `500`.
- **Propiedad:** backend confirma el dueño y aplica transiciones; el cliente no define dueño.
- **Datos:** actualiza `CONVERSATIONS`; cierre/archivo no elimina mensajes ni cambia estado de problemas.

#### API-007 — Listar mensajes de conversación

- **Método/ruta:** `GET /api/v1/conversations/{conversation_id}/messages`
- **Autenticación/permisos:** Bearer válido, propietario de la conversación.
- **Query:** `limit`, `cursor`; orden cronológico ascendente estable (`created_at`, `id`).
- **Body:** ninguno.
- **Éxito:** `200 OK`, `{ "items": [{"id":"ab66c63c-ec48-45aa-8ced-64a349401bb8","role":"installer","content_text":"La cámara no muestra imagen","processing_state":"completed","created_at":"2026-11-14T14:30:00Z","issue_ids":["f965a003-5be2-4fb4-a17a-3cfd19d2ea85"],"media_ids":[]}], "next_cursor": null }`.
- **Errores:** `400`, `401`, `404`, `422`, `500`.
- **Propiedad:** verificar conversación propia antes de listar.
- **Datos:** `MESSAGES`, `MESSAGE_ISSUES`, metadatos autorizados de `MEDIA_ASSETS`; excluir prompts internos y datos de proveedor innecesarios.

## 6. Chat, problemas y análisis IA

#### API-008 — Enviar mensaje y obtener respuesta del asistente

- **Método/ruta:** `POST /api/v1/conversations/{conversation_id}/messages`
- **Autenticación/permisos:** Bearer válido; conversación propia, no archivada/cerrada para escritura según regla de estado aprobada.
- **Headers:** `Idempotency-Key` UUID obligatorio propuesto para evitar duplicar un turno al reintentar.
- **Body:** `content_text` (string, puede omitirse solo si `media_ids` contiene al menos una imagen cargada), `media_ids` (lista UUID opcional), `issue_ids` (lista UUID opcional solo para continuar problemas existentes; cada problema debe pertenecer a esta conversación y usuario). Cliente no asigna propietario, hipótesis, diagnóstico ni resultado.
- **Ejemplo:** `{"content_text":"La cámara prende pero no aparece imagen en el grabador","media_ids":["51a7ba11-034c-4d63-9314-e30cfda4219c"],"issue_ids":[]}`
- **Éxito propuesto:** `201 Created` cuando persistieron el turno y la respuesta final. `{"user_message":{"id":"ab66c63c-ec48-45aa-8ced-64a349401bb8","role":"installer","processing_state":"completed","created_at":"2026-11-14T14:30:00Z"},"assistant_message":{"id":"c2a54664-9ba2-4a9a-8079-7503975827b4","role":"assistant","content_text":"¿La cámara aparece en la lista de canales del grabador?","processing_state":"completed","created_at":"2026-11-14T14:30:02Z"},"issues":[{"id":"f965a003-5be2-4fb4-a17a-3cfd19d2ea85","state":"awaiting_input"}],"recommendations":[]}`. El proveedor/modelo, cuando se necesiten para trazabilidad, se guardan solo en backend y no es necesario exponerlos al instalador.
- **Errores:** `400` mensaje vacío sin adjunto, `401`, `404` conversación/adjunto/problema no propio, `409` estado o idempotencia, `413/415` adjuntos, `422`, `429`, `502` proveedor, `503`, `504`, `500` persistencia.
- **Propiedad y reglas:** el backend establece identidad, carga solo adjuntos propios y vincula cada mensaje a problemas explícitos/determinados por diagnóstico. Nunca mezcla síntomas ni asigna un problema ajeno. Hipótesis no son diagnósticos. El backend aplica reglas de seguridad y valida la respuesta antes de guardarla/devolverla. Un resultado parcial/temporal nunca resuelve el problema.
- **Datos:** crea `MESSAGES`, `MESSAGE_ISSUES` y según diagnóstico `TECHNICAL_ISSUES`, `ISSUE_UNKNOWNS`, `ISSUE_HYPOTHESES`, `HYPOTHESIS_EVIDENCE`, `RECOMMENDATIONS`, `RECOMMENDATION_STEPS`, `ISSUE_STATUS_EVENTS`; actualiza actividad de `CONVERSATIONS`; consulta `MEDIA_ASSETS`, `MEMORY_ITEMS`, y solo versiones vigentes autorizadas de conocimiento compartido. El turno se persiste antes o de forma transaccional con procesamiento para evitar pérdida silenciosa.
- **Modo de interacción:** este contrato propone operación síncrona. Duración del timeout, streaming y procesamiento asíncrono no se han aprobado; confirmar antes de implementación integrada. No introducir cola/background worker sin aprobación.

#### API-009 — Consultar problemas de una conversación

- **Método/ruta:** `GET /api/v1/conversations/{conversation_id}/issues`
- **Autenticación/permisos:** Bearer válido y propietario.
- **Query:** `limit`, `cursor`, `state` opcional.
- **Solicitud:** sin body.
- **Éxito:** `200 OK`, `{ "items": [{"id":"f965a003-5be2-4fb4-a17a-3cfd19d2ea85","initial_symptom":"La cámara prende pero no aparece imagen","interpreted_description":null,"state":"awaiting_input","started_at":"2026-11-14T14:30:00Z","updated_at":"2026-11-14T14:30:02Z"}], "next_cursor": null }`.
- **Errores:** `400`, `401`, `404`, `422`, `500`.
- **Propiedad:** conversación propia.
- **Datos:** `TECHNICAL_ISSUES`.

#### API-010 — Consultar detalle de problema, hipótesis y datos faltantes

- **Método/ruta:** `GET /api/v1/issues/{issue_id}`
- **Autenticación/permisos:** Bearer válido y propietario indirecto/directo.
- **Query:** ninguno.
- **Solicitud:** sin body.
- **Éxito:** `200 OK`, `{"id":"f965a003-5be2-4fb4-a17a-3cfd19d2ea85","conversation_id":"d00c1c11-6100-442f-85f2-634a6b0e77d2","initial_symptom":"La cámara prende pero no aparece imagen","state":"diagnosing","equipment":[{"equipment_type":"cámara","brand":null,"model":null}],"hypotheses":[{"id":"b01b2ea6-d18d-4467-95a8-7a1c13c301a8","description":"Posible problema de canal o compatibilidad","state":"candidate","evidence":[]}],"unknowns":[{"id":"18a0f7e3-a9bf-460f-8afc-35a1d237ee3b","unknown_item":"Si el grabador detecta la cámara","state":"pending","question_text":"¿La cámara aparece en la lista de canales?"}]}`.
- **Errores:** `400`, `401`, `404`, `500`.
- **Propiedad:** comprobar dueño de problema/conversación; devolución 404 para ajeno.
- **Datos:** `TECHNICAL_ISSUES`, `ISSUE_EQUIPMENT`, `EQUIPMENT_MENTIONS`, `ISSUE_HYPOTHESES`, `HYPOTHESIS_EVIDENCE`, `ISSUE_UNKNOWNS`.

#### API-011 — Registrar evidencia de una hipótesis

- **Método/ruta:** `POST /api/v1/issues/{issue_id}/hypotheses/{hypothesis_id}/evidence`
- **Autenticación/permisos:** Bearer válido, propietario. Evitar este endpoint si la evidencia ya se registra dentro del turno de chat; se incluye para registro estructurado explícito.
- **Headers:** `Idempotency-Key` obligatorio.
- **Body:** `source_message_id` UUID propio y asociado al problema, `evidence_kind` (`installer_report`, `visual_observation`, `check_result`, `other_observation`), `evidence_note` no vacío.
- **Ejemplo:** `{"source_message_id":"ab66c63c-ec48-45aa-8ced-64a349401bb8","evidence_kind":"installer_report","evidence_note":"El instalador indica que el canal no aparece en la lista."}`
- **Éxito:** `201 Created`, `{"id":"f6a013c2-a46a-4ab0-a3b4-81e5d54b8a38","issue_id":"f965a003-5be2-4fb4-a17a-3cfd19d2ea85","evidence_kind":"installer_report","created_at":"2026-11-14T14:33:00Z"}`.
- **Errores:** `401`, `404` problema/mensaje no propio o no asociado, `409` clave repetida con distinto body, `422`, `500`.
- **Propiedad:** mensaje, hipótesis y problema deben ser del mismo instalador/conversación; el backend verifica todas las relaciones.
- **Datos:** `HYPOTHESIS_EVIDENCE`; no crea ni confirma una hipótesis. La necesidad de esta ruta además de la persistencia por chat debe confirmarse antes de implementación.

## 7. Fotografías privadas

Los formatos/cantidad/tamaño concretos aún requieren validación con el modelo y proveedor seleccionados. Como propuesta inicial heredada de requisitos: JPEG/JPG, PNG y WebP; máximo tres fotos por mensaje y 10 MB por archivo. Estos límites no son compromisos aprobados y solo se aplicarán tras aprobación/configuración. FastAPI valida extensión, MIME declarado y tipo real, tamaño, propietario y cuota antes de procesar. Los binarios quedan en Supabase Storage privado; PostgreSQL conserva metadatos/ruta no pública.

#### API-012 — Cargar una fotografía a conversación

- **Método/ruta:** `POST /api/v1/conversations/{conversation_id}/media`
- **Autenticación/permisos:** Bearer válido y dueño de conversación.
- **Headers/body:** `multipart/form-data`, campo `file` obligatorio, `Idempotency-Key` UUID. Este contrato propone carga transmitida por FastAPI; URL firmada de carga directa queda como alternativa pendiente y no debe usarse sin aprobar su control de acceso.
- **Ejemplo de solicitud:** multipart con `file=@camara.jpg` (no JSON).
- **Éxito:** `201 Created`, `{"id":"51a7ba11-034c-4d63-9314-e30cfda4219c","conversation_id":"d00c1c11-6100-442f-85f2-634a6b0e77d2","message_id":null,"mime_type":"image/jpeg","size_bytes":482100,"upload_state":"uploaded","analysis_state":"not_requested","created_at":"2026-11-14T14:35:00Z"}`. El archivo aún no se vincula a mensaje/problema hasta el envío del turno; no aceptar `owner_user_id`, `object_key` ni ruta del Storage del cliente.
- **Errores:** `400` body/form-data inválido, `401`, `404` conversación no propia, `409` duplicidad idempotente, `413`, `415`, `422` imagen ilegible/corrupta o límites, `429`, `502/503` Storage, `500`.
- **Propiedad:** el backend crea objeto con ruta aleatoria bajo espacio privado del usuario; jamás confía en path enviado por frontend. Validación real de MIME y propietario.
- **Datos:** inserta objeto en Supabase Storage privado y metadatos `MEDIA_ASSETS`; asociación `ISSUE_MEDIA` ocurre cuando se vincula con el problema durante API-008. La transacción PostgreSQL/Storage y compensación ante fallo deben definirse en implementación.

#### API-013 — Consultar o descargar fotografía privada

- **Método/ruta:** `GET /api/v1/media/{media_id}`
- **Autenticación/permisos:** Bearer válido, propietario del archivo y de conversación.
- **Parámetros:** `media_id` UUID.
- **Body:** ninguno.
- **Éxito:** `200 OK` con el contenido binario, `Content-Type` detectado, `Content-Length` y `Cache-Control: private, no-store`. El contrato no devuelve URL pública ni clave de Storage.
- **Errores:** `401`, `404` inexistente/no propio/retirado, `410` si se adopta explícitamente como recurso retirado, `502/503` Storage, `500`.
- **Propiedad:** autorización del backend en cada descarga; RLS/Storage privado como defensa adicional.
- **Datos:** lee `MEDIA_ASSETS` y objeto privado de Supabase Storage. La descarga no concede permiso de compartir.

#### API-014 — Retirar acceso a una fotografía privada

- **Método/ruta:** `DELETE /api/v1/media/{media_id}`
- **Autenticación/permisos:** Bearer válido y propietario.
- **Body:** ninguno.
- **Éxito:** `200 OK`, `{"id":"51a7ba11-034c-4d63-9314-e30cfda4219c","upload_state":"deletion_pending","removed_at":"2026-11-14T14:40:00Z"}`. Acepta retiro lógico/impide accesos nuevos; no afirma purga física inmediata ni define un proceso asíncrono de eliminación.
- **Errores:** `401`, `404`, `409` si se requiere resolver vínculo/consentimiento, `500`, `503`.
- **Propiedad:** solo dueño puede solicitarlo; backend retira vínculos compartidos asociados si corresponde e inicia proceso autorizado.
- **Datos:** `MEDIA_ASSETS`, `ISSUE_MEDIA`, `PHOTO_CONSENT_EVENTS`, `SHARED_CASE_PHOTOS`, Storage. Retención física/backups sigue pendiente; esta ruta no inventa plazo.

## 8. Recomendaciones y resultados

#### API-015 — Listar recomendaciones de problema

- **Método/ruta:** `GET /api/v1/issues/{issue_id}/recommendations`
- **Autenticación/permisos:** Bearer válido y propietario.
- **Query:** `limit`, `cursor`; ordenar por fecha de creación y orden de recomendación.
- **Body:** ninguno.
- **Éxito:** `200 OK`, `{ "items": [{"id":"d2a81450-1eb8-4b00-b6c0-44a721f18f16","summary":"Revisar si el canal recibe señal","risk_level":"low","warning_text":null,"expected_result":"El canal muestra video en vivo","workflow_state":"awaiting_result","steps":[{"step_number":1,"instruction":"Abre la vista de canales del grabador.","expected_observation":"Indica si el canal aparece y qué mensaje muestra."}],"created_at":"2026-11-14T14:36:00Z"}], "next_cursor": null }`.
- **Errores:** `400`, `401`, `404`, `422`, `500`.
- **Propiedad:** issue propio.
- **Datos:** `RECOMMENDATIONS`, `RECOMMENDATION_STEPS`.

#### API-016 — Consultar detalle e historial de resultados de recomendación

- **Método/ruta:** `GET /api/v1/recommendations/{recommendation_id}`
- **Autenticación/permisos:** Bearer válido y dueño del problema vinculado.
- **Query:** `results_limit` opcional, `results_cursor` opcional.
- **Body:** ninguno.
- **Éxito:** `200 OK`, objeto de API-015 más `results:[{"id":"bb73d700-640d-4eb6-9086-8f8a072e9aae","outcome":"not_tested","result_description":null,"reported_at":"2026-11-14T14:36:00Z"}]`.
- **Errores:** `400`, `401`, `404`, `422`, `500`.
- **Propiedad:** valida recomendación, issue y usuario.
- **Datos:** `RECOMMENDATIONS`, `RECOMMENDATION_STEPS`, `CHECK_RESULTS`.

#### API-017 — Registrar resultado informado por instalador

- **Método/ruta:** `POST /api/v1/recommendations/{recommendation_id}/results`
- **Autenticación/permisos:** Bearer válido y propietario.
- **Headers:** `Idempotency-Key` UUID obligatorio propuesto.
- **Body:** `outcome` requerido y limitado a `confirmed_success`, `partial_improvement`, `temporary_success`, `failed`, `not_tested`, `ambiguous`; `result_description` opcional; `evidence_message_id` opcional, debe ser mensaje propio/contextual. El cliente no envía nuevo estado de issue.
- **Ejemplo:** `{"outcome":"partial_improvement","result_description":"Ahora se ve por momentos, pero vuelve a perder imagen.","evidence_message_id":"ab66c63c-ec48-45aa-8ced-64a349401bb8"}`
- **Éxito:** `201 Created`, `{"id":"bb73d700-640d-4eb6-9086-8f8a072e9aae","recommendation_id":"d2a81450-1eb8-4b00-b6c0-44a721f18f16","issue_id":"f965a003-5be2-4fb4-a17a-3cfd19d2ea85","outcome":"partial_improvement","reported_at":"2026-11-14T14:40:00Z","issue_state":"partial_improvement","case_eligible":false}`.
- **Errores:** `400`, `401`, `404`, `409` transición/idempotencia, `422` outcome desconocido, `500` persistencia.
- **Propiedad:** el backend fija `owner_user_id` desde JWT y valida acceso a recomendación/mensaje. Solo `confirmed_success` explícito puede marcar problema resuelto y hacer elegible un caso privado. Mejora parcial/temporal, fallo, no probado o ambiguo nunca resuelven ni habilitan conocimiento compartido. No repetir una acción ya registrada sin justificación nueva.
- **Datos:** añade `CHECK_RESULTS`; si aplica actualiza `TECHNICAL_ISSUES` y añade `ISSUE_STATUS_EVENTS`; caso técnico solo tras resultado positivo confirmado. Respuestas a preguntas pendientes e información faltante se envían como mensaje normal por API-008, que vincula el turno al `ISSUE_UNKNOWNS` pertinente; el cliente no fija directamente estado de hipótesis o problema.

## 9. Memoria individual

La memoria no es una copia completa de mensajes. El backend recupera solo recuerdos técnicos pertinentes al usuario y al problema actual; nunca consulta memoria de otro usuario ni publica recuerdos automáticamente.

#### API-018 — Consultar memoria técnica propia

- **Método/ruta:** `GET /api/v1/memory`
- **Autenticación/permisos:** Bearer válido; solo propietario autenticado.
- **Query:** `state=active|archived`, `type` opcional, paginación común.
- **Body:** ninguno.
- **Éxito:** `200 OK`, `{ "items": [{"id":"95b862f2-6c38-4f67-b107-0b3fa58bcc30","memory_type":"equipment_context","summary":"El instalador mencionó un NVR de marca no identificada.","state":"active","issue_id":"f965a003-5be2-4fb4-a17a-3cfd19d2ea85","last_used_at":null,"created_at":"2026-11-14T14:40:00Z"}], "next_cursor": null }`.
- **Errores:** `400`, `401`, `422`, `500`.
- **Propiedad:** `owner_user_id` procede del JWT.
- **Datos:** `MEMORY_ITEMS`; no retornar conversación completa ni dato sensible innecesario.

#### API-019 — Registrar recuerdo técnico propio

- **Método/ruta:** `POST /api/v1/memory`
- **Autenticación/permisos:** Bearer válido; crear solo para usuario actual. Uso interno/explícito; extracción automática por IA requiere revisión/validación backend.
- **Headers:** `Idempotency-Key` UUID obligatorio.
- **Body:** `memory_type` entre `equipment_context`, `technical_context`, `procedure`, `confirmed_solution`; `summary` breve no vacío; `source_message_id` propio obligatorio; `issue_id` y `equipment_mention_id` opcionales, con relaciones propias.
- **Ejemplo:** `{"memory_type":"confirmed_solution","summary":"En este caso el instalador confirmó que el cambio de canal resolvió el problema.","source_message_id":"ab66c63c-ec48-45aa-8ced-64a349401bb8","issue_id":"f965a003-5be2-4fb4-a17a-3cfd19d2ea85","equipment_mention_id":null}`
- **Éxito:** `201 Created`, objeto de API-018.
- **Errores:** `401`, `404` fuentes no propias, `409`, `422`, `500`.
- **Propiedad:** backend valida propiedad de todas las fuentes y no almacena contraseña/credencial; no publica recuerdo.
- **Datos:** crea `MEMORY_ITEMS`; política de edición/retención requiere respetar decisión pendiente.

#### API-020 — Archivar o reactivar recuerdo propio

- **Método/ruta:** `PATCH /api/v1/memory/{memory_id}`
- **Autenticación/permisos:** Bearer válido y propietario.
- **Body:** `{"state":"archived"}` o `{"state":"active"}`. La política final de edición y borrado sigue pendiente.
- **Éxito:** `200 OK`, objeto de API-018 actualizado.
- **Errores:** `400`, `401`, `404`, `409`, `422`, `500`.
- **Propiedad:** backend verifica `owner_user_id`; no se puede cambiar propietario, fuente ni versión compartida.
- **Datos:** actualiza `MEMORY_ITEMS.state`, preservando fuente e historial conversacional.

## 10. Casos técnicos y conocimiento compartido

La vista compartible es una versión depurada e inmutable para consentimiento; no incluye usuario de origen, conversación, mensaje privado, token ni ubicación de archivo. El backend solo publica una versión exacta cuando verifica (a) `confirmed_success` informado por el instalador y (b) autorización afirmativa vigente para esa versión de texto. Fotografías requieren autorización individual adicional. Silencio y rechazo no autorizan. Revocar texto retira el caso inmediatamente de nuevas consultas; revocar una foto la retira sin inferir que se revocó el texto.

#### API-021 — Listar casos técnicos privados propios

- **Método/ruta:** `GET /api/v1/my/cases`
- **Autenticación/permisos:** Bearer válido; casos del usuario actual.
- **Query:** `state` opcional (`private_confirmed`, `shared`, `withdrawn`), `limit`, `cursor`.
- **Body:** ninguno.
- **Éxito:** `200 OK`, `{ "items": [{"id":"3dc79670-9b79-462c-97b0-17d1ee66bd7d","issue_id":"f965a003-5be2-4fb4-a17a-3cfd19d2ea85","state":"private_confirmed","confirmed_at":"2026-11-14T14:40:00Z","sharing_state":"not_authorized"}], "next_cursor": null }`.
- **Errores:** `400`, `401`, `422`, `500`.
- **Propiedad:** propietario derivado del JWT.
- **Datos:** `TECHNICAL_CASES`, `CHECK_RESULTS`, autorización propia; nunca filtra origen ajeno.

#### API-022 — Crear propuesta privada de caso desde problema confirmado

- **Método/ruta:** `POST /api/v1/issues/{issue_id}/case-proposals`
- **Autenticación/permisos:** Bearer válido, propietario; el problema debe estar resuelto por confirmación positiva completa.
- **Headers:** `Idempotency-Key` UUID obligatorio.
- **Body:** `{"include_media_ids":["51a7ba11-034c-4d63-9314-e30cfda4219c"]}` opcional; es una lista de candidatos, no consentimiento fotográfico. No permite enviar un diagnóstico/síntoma/solución que reemplace el registro original.
- **Ejemplo de respuesta:** `201 Created`, `{"case_id":"3dc79670-9b79-462c-97b0-17d1ee66bd7d","shared_case_id":"e98fc734-7e03-4c19-877f-c5efc0bec48b","version_id":"d42c3cdf-1770-47f7-899f-f410118b6fde","case_state":"private_confirmed","version_state":"draft","text_consent":"not_requested","photo_consent":"not_requested"}`.
- **Errores:** `401`, `404` problema/foto no propia, `409 CASE_NOT_CONFIRMED` o duplicado/conflicto, `422` relación no válida, `500`.
- **Propiedad:** solo propietario crea; el servidor valida resultado `confirmed_success` y que archivos pertenezcan al mismo caso. La selección de una foto no es autorización.
- **Datos:** crea `TECHNICAL_CASES`, `SHARED_CASES`, `SHARED_CASE_VERSIONS` en estado no publicado y registra fuente. La vista inicial debe quedar privada.

#### API-023 — Consultar borrador depurado y texto exacto para compartir

- **Método/ruta:** `GET /api/v1/my/cases/{case_id}/proposal`
- **Autenticación/permisos:** Bearer válido y propietario.
- **Query:** `version_id` UUID obligatorio si hay más de una versión; de otro modo la versión pendiente más reciente.
- **Body:** ninguno.
- **Éxito:** `200 OK`, `{"case_id":"3dc79670-9b79-462c-97b0-17d1ee66bd7d","version_id":"d42c3cdf-1770-47f7-899f-f410118b6fde","content":{"symptom_text":"La cámara no mostraba imagen en el grabador.","interpreted_symptom":null,"equipment":[{"equipment_type":"cámara","brand":null,"model":null}],"installation_context":null,"steps":[{"step_number":1,"procedure_summary":"Se revisó la asignación del canal.","result_summary":"El instalador informó que volvió la imagen.","outcome":"confirmed_success"}],"resolution_summary":"El instalador confirmó que el ajuste resolvió el problema en esta instalación.","limitations":"Experiencia de una instalación; no garantiza el resultado para otros modelos.","unknown_information":"Marca y modelo no identificados."},"content_digest":"sha256:...","consent_copy_version":"text-share-v1","consent_prompt":"¿Autorizas compartir este texto depurado con otros instaladores?"}`. El digest y copy version son generados por servidor; el ejemplo es ilustrativo, no un formato criptográfico aprobado.
- **Errores:** `401`, `404` no propio/no existe, `409` no hay confirmación positiva, `500`.
- **Propiedad:** solo titular; proyección se construye desde sus datos privados y muestra el contenido exacto de la versión candidata.
- **Datos:** `TECHNICAL_CASES`, `SHARED_CASE_VERSIONS`, equipos/pasos y resultado relacionado. No publica.

#### API-024 — Autorizar o rechazar compartir texto

- **Método/ruta:** `POST /api/v1/my/cases/{case_id}/text-consent`
- **Autenticación/permisos:** Bearer válido y propietario.
- **Headers:** `Idempotency-Key` UUID.
- **Body:** `version_id` UUID, `decision` (`granted` o `rejected`), `consent_copy_version` devuelta por API-023 y `content_digest` exacto devuelto por API-023. `granted` solo se envía tras acción afirmativa explícita. La opción de silencio no genera solicitud ni evento.
- **Ejemplo:** `{"version_id":"d42c3cdf-1770-47f7-899f-f410118b6fde","decision":"granted","consent_copy_version":"text-share-v1","content_digest":"sha256:..."}`.
- **Éxito:** `201 Created`, `{"case_id":"3dc79670-9b79-462c-97b0-17d1ee66bd7d","version_id":"d42c3cdf-1770-47f7-899f-f410118b6fde","decision":"granted","publication_state":"published","occurred_at":"2026-11-14T14:50:00Z"}`. Publicar solo después de validar transaccionalmente éxito positivo, digest/version y autorización. Si el backend no puede completar de forma consistente el registro y publicación, no devolver éxito; conservar una respuesta segura e idempotente según la transacción implementada.
- **Errores:** `401`, `403` consentimiento/confirmación insuficiente, `404`, `409` versión/digest ya no vigente, `422`, `500`.
- **Propiedad:** FastAPI verifica dueño y registra decisión; el cliente nunca escribe filas ni marca `published` directamente.
- **Datos:** agrega `CASE_TEXT_CONSENT_EVENTS`; cuando se concede, escribe procedencia y eventos de publicación y cambia `SHARED_CASES`/versión solo tras todas las comprobaciones. Rechazo se registra y permanece privado.

#### API-025 — Autorizar o rechazar compartir una fotografía

- **Método/ruta:** `POST /api/v1/my/cases/{case_id}/photo-consents`
- **Autenticación/permisos:** Bearer válido y dueño del caso/archivo.
- **Headers:** `Idempotency-Key` UUID.
- **Body:** `version_id`, `media_id`, `decision` (`granted` o `rejected`), `consent_copy_version`. Afirmación explícita afecta solo esa foto y versión.
- **Ejemplo:** `{"version_id":"d42c3cdf-1770-47f7-899f-f410118b6fde","media_id":"51a7ba11-034c-4d63-9314-e30cfda4219c","decision":"granted","consent_copy_version":"photo-share-v1"}`.
- **Éxito:** `201 Created`, `{"media_id":"51a7ba11-034c-4d63-9314-e30cfda4219c","version_id":"d42c3cdf-1770-47f7-899f-f410118b6fde","decision":"granted","photo_available_in_shared_case":true,"occurred_at":"2026-11-14T14:51:00Z"}`. El permiso textual vigente es requisito separado para mostrar una foto adjunta al caso compartido.
- **Errores:** `401`, `403`, `404`, `409` versión/caso no coinciden o caso no publicado, `422`, `500`.
- **Propiedad:** servidor verifica propiedad de caso y foto, versión exacta, permiso de texto y permiso fotográfico. No acepta object key/URL del cliente.
- **Datos:** `PHOTO_CONSENT_EVENTS`, `SHARED_CASE_PHOTOS`, `MEDIA_ASSETS`; Storage continúa privado y solo backend sirve acceso condicionado.

#### API-026 — Revocar autorización textual

- **Método/ruta:** `POST /api/v1/my/cases/{case_id}/text-consent/revocations`
- **Autenticación/permisos:** Bearer válido y titular del caso.
- **Headers:** `Idempotency-Key` UUID.
- **Body:** `version_id` y `consent_event_id` autorizado a revocar; `reason` opcional.
- **Ejemplo:** `{"version_id":"d42c3cdf-1770-47f7-899f-f410118b6fde","consent_event_id":"d1386941-46a7-4e1d-ad11-6c70e1d50ca9","reason":"Ya no deseo compartirlo."}`.
- **Éxito:** `200 OK`, `{"case_id":"3dc79670-9b79-462c-97b0-17d1ee66bd7d","version_id":"d42c3cdf-1770-47f7-899f-f410118b6fde","decision":"revoked","publication_state":"withdrawn","excluded_from_new_searches":true,"occurred_at":"2026-11-14T15:00:00Z"}`. La retirada lógica de consultas nuevas ocurre antes de responder; la purga física/backups queda fuera de este resultado.
- **Errores:** `401`, `403`, `404`, `409` evento ya revocado/no corresponde, `422`, `500`.
- **Propiedad:** solo propietario revoca su autorización; backend registra evento append-only y retira la versión de consultas nuevas inmediatamente.
- **Datos:** `CASE_TEXT_CONSENT_EVENTS`, `SHARED_CASES`, `SHARED_CASE_VERSIONS`, `CASE_PUBLICATION_PROVENANCE`, `SHARED_CASE_EVENTS`. No afirma purga de backups o enlaces ya servidos; política pendiente.

#### API-027 — Revocar autorización fotográfica

- **Método/ruta:** `POST /api/v1/my/cases/{case_id}/photo-consent-revocations`
- **Autenticación/permisos:** Bearer válido y dueño del caso/foto.
- **Headers:** `Idempotency-Key` UUID.
- **Body:** `version_id`, `media_id`, `consent_event_id`, `reason` opcional.
- **Ejemplo:** `{"version_id":"d42c3cdf-1770-47f7-899f-f410118b6fde","media_id":"51a7ba11-034c-4d63-9314-e30cfda4219c","consent_event_id":"91af1a43-a067-4e7d-a11e-54c3f81bb61f"}`.
- **Éxito:** `200 OK`, `{"media_id":"51a7ba11-034c-4d63-9314-e30cfda4219c","decision":"revoked","excluded_from_new_photo_access":true,"occurred_at":"2026-11-14T15:01:00Z"}`. Se impiden nuevas entregas de la foto antes de responder.
- **Errores:** `401`, `403`, `404`, `409`, `422`, `500`.
- **Propiedad:** verifica que evento y archivo correspondan a dueño/caso/version; no revoca autorización de texto.
- **Datos:** `PHOTO_CONSENT_EVENTS`, `SHARED_CASE_PHOTOS`; retirar la referencia y bloquear entregas nuevas sin cambiar el consentimiento textual. Retención física pendiente.

#### API-028 — Retirar caso propio del conocimiento compartido

- **Método/ruta:** `POST /api/v1/my/cases/{case_id}/withdrawals`
- **Autenticación/permisos:** Bearer válido y propietario.
- **Headers:** `Idempotency-Key` UUID.
- **Body:** `reason` opcional.
- **Ejemplo:** `{"reason":"El contexto del equipo cambió."}`.
- **Éxito:** `200 OK`, `{"case_id":"3dc79670-9b79-462c-97b0-17d1ee66bd7d","state":"withdrawn","excluded_from_new_searches":true,"occurred_at":"2026-11-14T15:02:00Z"}`. Retiro lógico completado antes de responder.
- **Errores:** `401`, `404`, `409`, `422`, `500`.
- **Propiedad:** solo origen puede solicitar el retiro; FastAPI retira publicación inmediatamente. No borra historial de autorización ni promete purga de copias/backups.
- **Datos:** `TECHNICAL_CASES`, `SHARED_CASES`, `SHARED_CASE_VERSIONS`, `SHARED_CASE_EVENTS`, y permisos relacionados según evento.

#### API-029 — Buscar casos compartidos vigentes

- **Método/ruta:** `GET /api/v1/knowledge/cases`
- **Autenticación/permisos:** Bearer válido; instalador autenticado.
- **Query:** `q` texto opcional; `equipment_type`, `brand`, `model` opcionales; paginación común. No admite propietario, identificadores de origen ni filtros sobre información privada.
- **Ejemplo de solicitud:** `GET /api/v1/knowledge/cases?q=c%C3%A1mara%20sin%20imagen&equipment_type=camera&limit=20`
- **Éxito:** `200 OK`, `{ "items": [{"id":"e98fc734-7e03-4c19-877f-c5efc0bec48b","version_id":"d42c3cdf-1770-47f7-899f-f410118b6fde","symptom_text":"La cámara no mostraba imagen en el grabador.","equipment":[{"equipment_type":"cámara","brand":null,"model":null}],"resolution_summary":"El instalador indicó que el ajuste resolvió este caso.","limitations":"Experiencia contextual; no garantiza el resultado en otros modelos.","published_at":"2026-11-14T14:50:00Z","photos":[]}], "next_cursor": null }`.
- **Errores:** `400` filtro/cursor inválido, `401`, `422`, `429`, `500`, `503` búsqueda no disponible.
- **Propiedad:** acceso autenticado solo a versión actual publicada y campos depurados; backend aplica vigencia de consentimiento/revocación.
- **Datos:** `SHARED_CASES`, `SHARED_CASE_VERSIONS`, `SHARED_CASE_EQUIPMENT`, `SHARED_CASE_STEPS`, fotos autorizadas si existen. Búsqueda textual/filtros estructurados como interfaz; índice/motor y criterio de relevancia siguen pendientes.

#### API-030 — Consultar caso compartido

- **Método/ruta:** `GET /api/v1/knowledge/cases/{shared_case_id}`
- **Autenticación/permisos:** Bearer válido y publicación vigente.
- **Parámetros:** UUID de caso compartido.
- **Body:** ninguno.
- **Éxito:** `200 OK`, mismo esquema de un `items[]` de API-029 con detalle de pasos, resultados reportados, límites y desconocidos; nunca identidad, conversación ni procedencia privada.
- **Errores:** `400`, `401`, `404` no publicado/retirado/no disponible, `500`.
- **Propiedad:** todo instalador autenticado puede consultar solo versión actual publicada. Las fotografías requieren autorización vigente independiente y se sirven mediante acceso privado controlado.
- **Datos:** versión actual de `SHARED_CASES`, versiones, equipos, pasos y referencias de foto validadas; omite `CASE_PUBLICATION_PROVENANCE` y eventos privados.

## 11. Contrato backend–proveedor IA

OpenAI API es el primer candidato multimodal a evaluar, no proveedor ni modelo definitivamente seleccionados. Solo FastAPI conserva credenciales del proveedor en configuración segura del servidor. El navegador nunca envía claves de proveedor, prompts de sistema ni tokens de servicio.

### 11.1 Flujo de procesamiento

Para API-008 FastAPI debe, en este orden lógico:

1. Validar JWT, estado de conversación, propiedad de problema(s) y propiedad/estado de cada archivo adjunto.
2. Validar cuerpo, longitud/cuotas y clave de idempotencia; persistir el mensaje del instalador sin aceptar owner, diagnóstico ni resultado provistos por el cliente.
3. Resolver los vínculos del mensaje a problemas existentes o crear problema(s) separados cuando el relato describa síntomas independientes. Si no está claro si es un problema nuevo, solicitar aclaración, no mezclar.
4. Recuperar solo los mensajes/contexto técnico pertinentes de esa conversación, recuerdos `MEMORY_ITEMS` del mismo usuario relevantes al síntoma/equipo, y casos compartidos actualmente publicados y autorizados que cumplan filtros de aplicabilidad. No enviar historial completo ni procedencia privada innecesaria.
5. Obtener las imágenes privadas a las que el usuario tiene acceso. Transmitir texto e imágenes necesarios al proveedor aprobado usando el mecanismo multimodal elegido. No generar URL pública permanente. Modelo, modalidad de imagen y política de transferencia siguen pendientes de evaluación de costo, calidad y privacidad.
6. Solicitar salida acotada y validable, tratar el resultado como propuesta no confiable, validar estructura, lenguaje, riesgos, equipo/contexto, y bloquear recomendaciones de alto impacto no verificables. No guardar razonamiento interno del modelo.
7. Persistir mensaje del asistente, estado de procesamiento, referencias a problema(s), hipótesis/evidencia, recomendaciones/pasos y metadatos mínimos del proveedor/modelo cuando sea necesario. Nunca registrar clave, prompt del sistema completo, chain-of-thought, ni payload de imagen en logs.
8. Devolver respuesta sin exponer claves internas. Si proveedor falla, conservar el mensaje del instalador ya guardado, no fabricar respuesta y permitir reintento seguro.

### 11.2 Forma lógica de la salida IA

Esquema interno propuesto para validar antes de persistir; no es endpoint del proveedor ni se expone literalmente como respuesta pública:

```json
{
  "assistant_text": "¿La cámara aparece en la lista de canales del grabador?",
  "issues": [{"client_reference": null, "symptom_summary": "No aparece imagen en el grabador", "state": "awaiting_input"}],
  "observations": [{"source": "installer_text", "statement": "El instalador indica que la cámara enciende"}],
  "hypotheses": [{"description": "Posible problema de canal o compatibilidad", "state": "candidate", "evidence_refs": []}],
  "unknowns": [{"item": "Si el grabador detecta la cámara", "question": "¿La cámara aparece en la lista de canales?"}],
  "recommendations": [],
  "safety_warnings": [],
  "limitations": ["No se identificó marca ni modelo en la información disponible"]
}
```

Los campos estructurados son una propuesta de implementación; el esquema exacto y proveedor/modelo se aprueban antes de integración. El backend descarta propiedades extra/no válidas, comprueba que hipótesis no se etiqueten como diagnóstico confirmado, y permite a la IA responder solicitando datos cuando falten. Una imagen borrosa o etiqueta no legible debe producir incertidumbre explícita, no una identificación inventada.

## 12. Seguridad y autorización transversal

- Todas las rutas privadas ejecutan validación JWT, autorización por recurso y consultas limitadas por dueño; identificadores UUID no sustituyen autorización.
- RLS se usa como defensa en profundidad en tablas privadas/Storage; reglas específicas, conexión FastAPI a PostgreSQL y uso eventual de rol privilegiado siguen pendientes. No dar por habilitado acceso directo desde React a tablas privadas.
- No exponer claves privadas/secretas de OpenAI, Supabase, Storage ni credenciales de base de datos en bundles, variables públicas del frontend, respuestas o logs. El mecanismo de autenticación que satisfaga además el requisito de no exponer claves Supabase debe definirse; ver pendientes.
- Supabase Storage permanece privado; FastAPI media permisos/descargas. Las claves de objeto son internas y nunca retornan en DTO.
- Validar JSON, tipos, UUID, longitud, MIME real y bytes; sanitizar para visualización. Valores máximos de solicitudes y reglas de límite se deben definir antes de despliegue; responder `429` al superar límites.
- La publicación de conocimiento es backend-only. Consentimientos son eventos explícitos e independientes ligados a texto/versiones o foto/versión. No endpoint de cliente puede fijar `publication_state`.
- Registrar request id, actor UUID interno, operación, resultado, recurso y fecha de acciones sensibles (confirmación, autorización/rechazo/revocación, publicación/retiro) minimizando datos. Nunca registrar credenciales, texto privado no necesario, imagen, prompt ni stack trace.
- Aplicar CORS con orígenes de despliegue aprobados; no usar comodín con credenciales. Orígenes y política CSRF/cookies dependen de estrategia de sesión pendiente.
- `404` uniforme para ocultar existencia de recursos ajenos cuando corresponda.

## 13. Matriz de correspondencia API–modelo

| Módulo | Endpoints | Entidades principales | Operación/validación principal |
|---|---|---|---|
| Salud | Health | Ninguna | Disponibilidad proceso; no filtrar configuración. |
| Perfil | API-001–002 | `INSTALLER_PROFILES`, Supabase Auth externo | `sub` fija el usuario; solo `display_name` editable. |
| Conversaciones | API-003–007 | `CONVERSATIONS`, `MESSAGES`, `TECHNICAL_ISSUES`, `MESSAGE_ISSUES`, `MEDIA_ASSETS` | Todas las filas verifican dueño y conversación. |
| Chat/IA | API-008 | `MESSAGES`, problemas, hipótesis, evidencias, recomendaciones, pasos, memoria y casos compartidos | Contexto mínimo; valida respuesta/riesgo; proveedor solo backend. |
| Diagnóstico | API-009–011 | `TECHNICAL_ISSUES`, `ISSUE_UNKNOWNS`, `ISSUE_HYPOTHESES`, `HYPOTHESIS_EVIDENCE`, equipo/mensajes | Hipótesis no es diagnóstico; mensaje y evidencia deben compartir propietario/issue. |
| Fotografías | API-012–014 | `MEDIA_ASSETS`, `ISSUE_MEDIA`, Storage privado y consentimiento si aplica | MIME/tamaño real; privado por defecto; sin URL pública. |
| Recomendaciones/resultado | API-015–017 | `RECOMMENDATIONS`, `RECOMMENDATION_STEPS`, `CHECK_RESULTS`, `ISSUE_STATUS_EVENTS`, `TECHNICAL_ISSUES` | Enum cerrado; solo éxito completo resuelve y habilita caso. |
| Memoria | API-018–020 | `MEMORY_ITEMS` y referencias privadas | `owner_user_id` desde JWT; no autopublicar; recuperar solo pertinencia. |
| Casos privados y consentimiento | API-021–028 | `TECHNICAL_CASES`, `SHARED_CASES`, `SHARED_CASE_VERSIONS`, eventos de consentimiento/publicación, provenance, fotos | Confirmación y permisos separados; publicación/revocación transaccionales/backend-only. |
| Conocimiento compartido | API-029–030 | `SHARED_CASES`, versión/equipo/pasos actuales, fotos autorizadas | Solo versión depurada vigente; filtro no expone origen. |

## 14. Inventario de rutas y cobertura funcional

#### API-000 — Comprobar salud del proceso FastAPI

- **Método/ruta:** `GET /api/v1/health`
- **Autenticación:** no requerida; respuesta no incluye datos internos.
- **Permisos:** acceso público solo para estado básico del proceso.
- **Parámetros/body:** ninguno.
- **Ejemplo de solicitud:** `GET /api/v1/health`.
- **Éxito:** `200 OK`, `{"status":"ok","request_id":"a47a8740-c929-42f2-bd04-e7611164ab16"}`.
- **Errores:** `503 SERVICE_UNAVAILABLE` si el proceso no atiende o se decide chequeo de dependencia, `500`; el endpoint no expone hostnames, versiones, secretos, estado detallado de Supabase/proveedor.
- **Autorización:** no accede a recursos del instalador.
- **Entidades:** ninguna.

Autenticación del proveedor no se cuenta como ruta FastAPI. Rutas API-001–030 quedan bajo `/api/v1`; el inventario no tiene ruta.

| Requisitos funcionales | Endpoints/contrato | Dependencias principales |
|---|---|---|
| RF-001–005 | Supabase Auth para alta/sesión; API-001–002 para perfil | Configuración/Auth, JWT y perfil. Flujos exactos pendientes. |
| RF-006–010 | API-003–008 | Auth, DB y proveedor IA para respuesta. |
| RF-011–015 | API-008, API-012–014 | Storage privado, validación binaria, modelo multimodal para análisis. |
| RF-016–020 | API-008–011 | Modelo IA; persistencia de problema/contexto/evidencia. |
| RF-021–023 | API-008, API-015–017 | IA validada por backend; reglas de riesgo. |
| RF-024–026 | API-017 | `CHECK_RESULTS`, transiciones issue. |
| RF-027–029 | API-003–007 | Auth, `CONVERSATIONS`/`MESSAGES`. |
| RF-030–032 | API-018–020 y recuperación interna API-008 | Memoria y aislamiento por usuario. |
| RF-033–035 | API-021–023 | Confirmación y datos privados de caso. |
| RF-036–039 | API-024, API-026, API-028–030 | Consentimiento textual, publicación, consulta; búsqueda sigue pendiente. |
| RF-040–043 | Todos privados; API-024–028 | JWT, RLS, Storage, auditoría y permisos independientes. |
| RF-044–050 | API-008, API-012, API-017 y formato común de error | Persistencia, red, IA, Storage y manejo de reintento. |

No se incluyen rutas de inventario, ventas, proveedores, precios, catálogo ni existencias.

> **Actualización 2026-11-19:** las rutas de inventario para reparaciones ya existen (sin ventas, proveedores ni precios). Ver [inventario-y-asistente.md](inventario-y-asistente.md).

## 15. Entregas sugeridas para implementación

1. **Configuración y salud:** base del monolito FastAPI, `/api/v1/health`, configuración por ambiente y logging con request id; sin claves en cliente.
2. **Autenticación y perfil:** aprobar antes proveedor/flujo de sesión y estrategia que no exponga claves Supabase al frontend; validar JWT en API y cerrar aislamiento/RLS. No usar datos reales hasta validar permisos.
3. **Conversaciones:** crear/listar/consultar/cerrar; perfil propio y almacenamiento con propietario.
4. **Chat de texto:** API-008 con proveedor de IA seleccionado, timeouts/reintento y persistencia usuario/asistente.
5. **Historial:** recuperar mensajes, estados y problemas independientes; validar idempotencia.
6. **Fotografías:** aprobar límites, carga (proxy vs firmada), política de Storage y transferencia al modelo; luego conectar análisis multimodal.
7. **Diagnóstico y recomendaciones:** problemas, incógnitas, hipótesis/evidencia, pasos y barreras de seguridad.
8. **Seguimiento:** outcomes cerrados y reglas de transición/resolución.
9. **Memoria individual:** extracción controlada, consulta pertinente, edición/archivo y aislamiento.
10. **Casos y conocimiento compartido:** vista depurada, consentimiento de texto/foto independiente, publicación, revocación y búsqueda; requiere cerrar consentimiento/RLS/retiro antes de activar.
11. **Validación integral:** pruebas de integración, autorización/RLS, privacidad, carga de imagen, fallos de IA, calidad de diagnóstico y accesibilidad conforme criterios aprobados.

Cada entrega se prueba funcionalmente antes de iniciar la siguiente. La secuencia es una propuesta de organización; no amplía alcance ni autoriza saltar aprobaciones requeridas.

## 16. Decisiones pendientes

| Decisión | Qué falta definir | Efecto | ¿Bloquea? | Hito recomendado |
|---|---|---|---|---|
| Supabase Auth y credenciales en cliente (**tensión documental**) | Arquitectura técnica sitúa las vistas de acceso integradas con Supabase Auth, mientras esta tarea prohíbe exponer cualquier clave de Supabase en frontend. Método registro/login/recuperación y proveedor SDK frente a fachada FastAPI no están decididos. No se debe inferir que la clave anónima esté permitida. | RF-001–005 y acceso a todas las rutas privadas | **Sí**, para autenticación real y API privada | Antes de API-001–008. Resolver expresamente esta tensión y acordar arquitectura compatible con la restricción de claves. |
| Validación JWT | JWKS/issuer/audience/rotación/revocación/expiración y refresh | Middleware de autenticación | **Sí**, antes de primer endpoint privado desplegado | Antes de autenticación. |
| Supabase/Postgres/RLS | Conexión FastAPI, contexto de usuario, uso de service role, políticas finales | Seguridad de todos los datos persistidos | **Sí**, antes de datos reales | Antes de persistencia real. |
| Base URL, hosting, CORS y sesión | Dominios, ambientes y cookies/headers/CSRF | URL, despliegue y controles navegador | No para contrato lógico; sí despliegue | Antes de integración frontend/despliegue. |
| Modo de chat | Síncrono vs asíncrono/streaming; API-008 adopta sync como propuesta | UX, estados, timeouts, reintento | **Sí** para congelar contrato; desarrollo UI preliminar posible | Antes de integrar IA. |
| Proveedor y modelo multimodal | Calidad, costo, privacidad, modalidad imagen, timeout | API-008, análisis de imagen y metadatos | No para UI/texto stub; sí IA real | Antes de integración multimodal. OpenAI candidato inicial, no decisión final. |
| Límite/tipo/cantidad de imagen | Propuesta JPEG/PNG/WebP, 3 por mensaje, 10 MB cada una debe validarse | API-012 y análisis | No para diseño; sí aceptación de upload | Antes de prueba integrada de foto. |
| Transporte de archivo | Proxy FastAPI (propuesto) o URL firmada; cuotas, antivirus/validación de bytes y compensación Storage/DB | API-012–014, revocación | Sí para carga/descarga real | Antes de módulo foto. |
| Retención y borrado | Datos, mensajes, memoria, archivos, cuentas, copias/backups y auditoría | API-014, cierre, privacidad | No para prototipo sin datos reales; **sí producción** | Antes de capturar datos reales/producción. |
| Compartir/consentir/revocar | Copia exacta, contenido depurado, texto de consentimiento, vigencia, retirada y URLs previas | API-022–028 | No bloquea chat privado; **sí conocimiento compartido** | Antes de activar casos compartidos. |
| Búsqueda y aplicabilidad de casos | Filtros/texto/semántica y ranking, no seleccionados | API-029–030 | No para persistir; sí calidad de consultas compartidas | Antes de habilitar conocimiento. |
| Estados/transiciones e idempotencia | Vocabulario final, reintentos y retención de claves idempotentes | API-006, 008, 017, 024–028 | No bloquea maqueta; sí persistencia consistente | Antes de backend estable. |
| Límites de tasa y cuota | Valores de límite por usuario/IP y tamaños de cuerpo | Seguridad/costos | No para documento; sí publicación externa | Antes de producción. |

### Clasificación por etapa

- **Necesario para comenzar implementación de UI y estructura de backend:** nombres de contrato, esquema lógico, respuesta de error y health aquí propuestos. Esto permite trabajo sin datos reales ni proveedor final.
- **Necesario antes de implementar autenticación privada:** flujo Supabase Auth, JWT y estrategia compatible con no exponer claves Supabase en React.
- **Puede cerrarse durante implementación inicial:** cursores, tamaño de página, nombres de estados definitivos, idempotencia, política de CORS y valores de rate limit, siempre antes de congelar QA/desplegar.
- **Bloquea módulos concretos:** proveedor multimodal bloquea IA real; política de imagen/Storage bloquea carga; política de consentimiento/revocación/búsqueda bloquea conocimiento compartido.
- **Bloquea producción con usuarios/datos reales:** RLS/conexión, retención/borrado, registro/auditoría, hosting/HTTPS, límites operativos y estrategia de seguridad.

## 17. Auditoría del contrato

- Los endpoints numerados cubren perfil, conversaciones, chat, archivos privados, diagnóstico, recomendaciones/resultados, memoria, casos y conocimiento compartido; health se lista aparte.
- Cada operación identifica método, ruta, autenticación/permisos, parámetros/body, ejemplo de solicitud/respuesta, códigos, regla de propiedad y entidades del modelo.
- Las rutas usan el prefijo `/api/v1`, UUID y fechas ISO 8601; se especifican paginación y errores uniformes.
- No se exponen credenciales de IA/Supabase ni claves/URLs de Storage; proveedor IA llamado solo por FastAPI.
- Confirmación positiva y autorización textual son independientes; el permiso fotográfico es separado. Silencio nunca autoriza. Revocación excluye inmediatamente de nuevas consultas sin prometer borrado de copias/backups no definido.
- Las categorías de resultado están cerradas y mejoras parciales/temporales no resuelven el problema ni habilitan publicación.
- Conversación y problema están separados; los problemas independientes no comparten evidencias/resultados sin asociación explícita.
- Endpoints y entidades corresponden al modelo conceptual; no se añaden tablas. Las rutas Auth del proveedor permanecen sin congelar por falta de decisión documentada. Se identifica la tensión entre la vista Auth prevista por la arquitectura y la prohibición actual de exponer cualquier clave Supabase en cliente.
- No se incluye inventario ni se modifica arquitectura. Las incertidumbres de proveedor, Auth, RLS, archivos, retención, búsqueda, modo de chat y rate limits quedan señaladas, no resueltas.

La especificación permite iniciar trabajo no dependiente (estructura del monolito, health y UI contractual), pero autenticación segura, persistencia real y módulos externos indicados no deben considerarse listos para producción hasta aprobar sus decisiones bloqueantes.



