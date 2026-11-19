# SecureAssist AI — Inventario para reparaciones y asistente local

**Fecha:** 2026-11-19
**Estado:** implementado en la rama `feature/inventario-y-chatbot`, pendiente de revisión.
**Relación con los demás documentos:** amplía `arquitectura-tecnica.md`, `modelo-datos.md`, `contratos-api.md` y `requisitos-funcionales-mvp.md`. Donde estos excluían el inventario, ahora remiten aquí. Lo que no se menciona en este documento sigue como estaba.

## 1. Decisiones del equipo

Se tomaron mientras Lina no estaba disponible. Se registran para que ella las revise en el Pull Request.

| # | Decisión | Motivo | Alternativa descartada |
|---|---|---|---|
| D-1 | Se **autoriza el inventario** de repuestos en bodega y de equipos instalados por cliente, con historial de reparaciones. | Los técnicos necesitan saber si hay un repuesto, dónde está y qué se le hizo antes a un equipo. | Catálogo con precios, compras, ventas y cotizaciones: **sigue fuera de alcance**. |
| D-2 | **PostgreSQL local en Docker** como almacenamiento de desarrollo, detrás de interfaces (puertos). | Permite trabajar sin credenciales de Supabase. El código de Supabase se conserva. | Esperar las credenciales de Supabase. |
| D-3 | **Ollama con `qwen3.5`** como proveedor de IA inicial, detrás del puerto `LanguageModel`. | Sin costo por uso y sin enviar datos a terceros. Es el modelo local probado que usa bien las herramientas. | OpenAI (costo); Gemini. OpenAI sigue siendo una opción: requiere solo un adaptador nuevo. |
| D-4 | **Roles** administrador y técnico. | Ver la sección 4. | Todos los usuarios con los mismos permisos. |
| D-5 | El asistente **solo consulta**: no registra ni modifica datos. | Evitar que un error del modelo altere existencias o reparaciones. | Herramientas de escritura con confirmación. |

Sigue pendiente: fotografías y análisis multimodal (los modelos locales disponibles no los resuelven bien), memoria individual y conocimiento compartido.

## 2. Arquitectura del backend

El monolito modular se organizó en capas para cumplir la inversión de dependencias: los casos de uso dependen de interfaces, no de Supabase, PostgreSQL ni Ollama.

```
app/
  domain/        entidades, errores de dominio y puertos (interfaces Protocol)
  application/   casos de uso: conversaciones, usuarios, inventario, asistente
  repositories/  adaptadores de datos: PostgreSQL, Supabase y memoria
  services/      adaptadores externos: Supabase Auth, login de prueba, Ollama
  api/routes/    traducción HTTP <-> casos de uso
  dependencies/  inyección con Depends; main.py es la raíz de composición
```

- **Puertos:** `ConversationRepository`, `UserRepository`, `CatalogRepository`, `ClientRepository`, `RepairRepository`, `AuthProvider` y `LanguageModel`. Se separan por agregado (segregación de interfaces).
- **Composición** (`main.py`): con `DATABASE_URL` se usa PostgreSQL; con `DEV_LOGIN` sin base, memoria; en otro caso, Supabase para las conversaciones. El inventario existe solo con PostgreSQL; sin él, sus rutas responden 503.
- **Errores de dominio** (`NotFoundError`, `ForbiddenError`, `ConflictError`, `StorageUnavailable`, `AssistantUnavailable`): se traducen a respuestas HTTP uniformes en `core/errors.py`.

## 3. Modelo de datos (PostgreSQL local)

Las migraciones están en `backend/migrations/postgres/` y se aplican al arrancar el backend.

| Tabla | Propósito |
|---|---|
| `app_users` | Usuario de la aplicación: id = `sub` del proveedor de identidad, rol y activo. |
| `conversations`, `messages` | Historial privado. `messages.role` ∈ {installer, assistant}. |
| `products` | Catálogo de repuestos: SKU único, categoría, marca, modelo y stock mínimo. **Sin precio.** |
| `stock_locations` | Bodegas, vehículos u otras ubicaciones. |
| `stock_levels` | Existencia por (producto, ubicación). `CHECK quantity >= 0`. |
| `stock_movements` | Libro de movimientos: entrada, salida, ajuste, reparación, traslado (entra/sale), con autor y nota. |
| `clients` | Clientes, con datos de contacto mínimos. |
| `installed_equipment` | Equipos instalados por cliente: tipo, marca, modelo, serial (único por marca), ubicación en el sitio y estado. |
| `repairs` | Reparación: cliente, equipo opcional, técnico, conversación opcional, falla, diagnóstico, solución y estado. |

Reglas garantizadas por la base o en una sola transacción:

- No hay stock negativo. Cada cambio de existencia tiene su movimiento. Una salida solo se aplica si alcanza (`UPDATE … WHERE quantity >= n`), así que dos técnicos no pueden consumir la misma última unidad.
- Los repuestos de una reparación son movimientos con `reason = 'repair'` y `repair_id`: no hay una tabla aparte que se pueda desincronizar.
- Una reparación cerrada (resuelta o cancelada) tiene `closed_at` y no admite cambios ni repuestos.
- Al abrir una reparación de un equipo, este pasa a «en reparación»; al cerrarla, vuelve a «operativo».
- Conversaciones: el aislamiento por propietario se aplica en cada consulta, más una clave foránea compuesta (conversación, propietario). En Supabase lo hace RLS (`migrations/001`, más `002` para los mensajes del asistente).

## 4. Roles y permisos

| Acción | Administrador | Técnico |
|---|---|---|
| Ver productos, disponibilidad por ubicación, bajo stock y movimientos | ✅ | ✅ (solo productos activos) |
| Crear o editar productos y ubicaciones; entradas, salidas, ajustes y traslados | ✅ | — |
| Registrar y editar clientes y equipos instalados | ✅ | ✅ |
| Ver el historial de reparaciones | ✅ | ✅ |
| Abrir reparaciones | ✅ | ✅ |
| Editar una reparación o agregarle repuestos | ✅ | Solo si es el técnico asignado |
| Gestionar usuarios y roles | ✅ | — |
| Ver conversaciones de otro usuario | — | — |

- Al iniciar sesión por primera vez, el usuario queda como técnico. Los correos de `ADMIN_EMAILS` siempre son administradores.
- Siempre debe quedar un administrador activo.

## 5. API (`/api/v1`)

La documentación interactiva está en `/docs` (entorno de desarrollo).

| Método y ruta | Uso |
|---|---|
| `GET /me` | Cuenta y rol del usuario actual. |
| `GET /users`, `PATCH /users/{id}` | Administración de roles y activación (solo administrador). |
| `GET/POST /products`, `GET/PATCH /products/{id}` | Catálogo con existencias (`q`, `category`, `low_stock`). |
| `GET/POST /locations`, `PATCH /locations/{id}` | Ubicaciones de stock. |
| `GET/POST /stock/movements`, `POST /stock/transfers` | Movimientos: `receipt`, `issue`, `adjustment` (`quantity` = conteo físico) y traslados. |
| `GET/POST /clients`, `GET/PATCH /clients/{id}` | Clientes; el detalle incluye sus equipos. |
| `POST /clients/{id}/equipment`, `GET/PATCH /equipment/{id}` | Equipos instalados; el detalle incluye su historial de reparaciones. |
| `GET/POST /repairs`, `GET/PATCH /repairs/{id}` | Reparaciones (`status`, `mine`, `client_id`, `equipment_id`). |
| `POST /repairs/{id}/parts` | Repuesto usado: descuenta el stock. |
| `POST /conversations/{id}/reply` | Respuesta del asistente al último mensaje del técnico. |

Los conflictos de negocio responden 409 con un código y un mensaje para mostrar al usuario: `INSUFFICIENT_STOCK`, `SKU_IN_USE`, `SERIAL_IN_USE`, `REPAIR_CLOSED`, `EQUIPMENT_CLIENT_MISMATCH`, `LAST_ADMIN`, `NO_CHANGE`, `NOTHING_TO_REPLY`.

## 6. Asistente conversacional

- **Flujo:** el técnico envía un mensaje (`POST …/messages`) y el frontend pide la respuesta (`POST …/reply`). El backend envía al modelo las instrucciones y los últimos 20 mensajes. Si el modelo pide herramientas, las ejecuta (máximo 3 rondas) y guarda la respuesta como mensaje `assistant`.
- **Instrucciones:** `app/application/assistant_prompt.py`, derivadas de `AGENTS.md` §4 y de `comportamiento-chatbot.md`:
  - Preguntar cuando falta información y no inventar.
  - Advertir los riesgos eléctricos.
  - Pedir confirmación del resultado.
  - No ofrecer acciones que no existen.
- **Herramientas de solo lectura:**
  - `consultar_inventario`: búsqueda por palabras, sin distinguir tildes, con existencias por ubicación.
  - `historial_equipo`: busca por serial, marca, modelo o cliente y devuelve las reparaciones anteriores.
- **Fallos:** si Ollama no responde, la ruta devuelve 503 `ASSISTANT_UNAVAILABLE` con un mensaje claro. El mensaje del técnico queda guardado y la interfaz ofrece reintentar.
- **Seguridad:**
  - Los argumentos del modelo se validan y recortan.
  - Los mensajes y los datos de las herramientas se tratan como información, no como instrucciones.
  - El texto del modelo se muestra con un Markdown mínimo construido con elementos de React, sin insertar HTML.
- **Limitaciones observadas con `qwen3.5`:** responde en 3 a 13 s en este equipo. Usa bien las herramientas y da cifras exactas, pero a veces es impreciso en detalles (por ejemplo, fechas relativas). La interfaz advierte que el asistente puede equivocarse.

## 7. Configuración

Ver `.env.example`:

- `DATABASE_URL`, `TEST_DATABASE_URL`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`
- `ADMIN_EMAILS`
- `LLM_PROVIDER` (`none` | `ollama`), `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `LLM_TIMEOUT_SECONDS`

## 8. Pruebas

- **Backend** (`pytest`):
  - Casos de uso con repositorios en memoria.
  - Integración contra PostgreSQL real (base `secureassist_test`), incluida la carrera de dos técnicos por la última unidad.
  - Asistente con un modelo falso y el adaptador de Ollama con transporte simulado.
  - Las pruebas de PostgreSQL se omiten si no está definido `TEST_DATABASE_URL`.
- **Frontend** (`npm test`): servicios de conversaciones, autenticación e inventario.

## 9. Pendiente

1. Que Lina revise y apruebe D-1 a D-5. También la nueva dependencia `asyncpg`, que `AGENTS.md` §9 exige autorizar.
2. Implementar los repositorios de inventario sobre Supabase si se mantiene Supabase como base de producción. Las tablas de `0002_inventory.sql` sirven de base, con RLS por rol.
3. Fotografías y análisis multimodal: requiere un modelo con visión (OpenAI u otro) y Supabase Storage.
4. Memoria individual y conocimiento compartido (según `modelo-datos.md`).
5. Título automático de las conversaciones a partir del primer mensaje.
