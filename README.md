# SecureAssist AI

Aplicación web en desarrollo para asistencia técnica a instaladores de sistemas de seguridad electrónica. Esta entrega contiene una pantalla mínima de estado y un backend FastAPI con `/api/v1/health`; no implementa el chatbot, autenticación, Supabase ni proveedor de IA.

## Requisitos locales

- Windows 10/11 y PowerShell.
- Python 3.10 o superior con `py` o `python` disponible en PATH.
- Node.js 18+ y npm.

## Backend (PowerShell)

Desde la raíz del proyecto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --app-dir backend --env-file .env --reload --host localhost --port 8000
```

Si `py` no está disponible pero `python` sí, sustituye `py -3` por `python`. Si PowerShell bloquea la activación del entorno, ejecuta en esa terminal `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y vuelve a activar.

La API queda en `http://localhost:8000`; documentación local en `http://localhost:8000/docs`. Comprueba salud con:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
```

## Frontend (otra terminal PowerShell)

```powershell
Set-Location frontend
Set-Content .env.local -Value 'VITE_API_BASE_URL=http://localhost:8000/api/v1'
npm install
npm run dev
```

Abre la URL que muestra Vite, normalmente `http://localhost:5173`. La aplicación consulta el endpoint real del backend configurado en `VITE_API_BASE_URL`. Para cambiarla, edita `frontend\.env.local` y reinicia Vite.

## Verificaciones

Backend, desde la raíz con el entorno activado:

```powershell
python -m pytest backend\tests -q
```

Frontend:

```powershell
Set-Location frontend
npm run typecheck
npm run build
```

La pantalla muestra conectado únicamente tras recibir y validar `status: "ok"` y un `request_id` del backend. No usa datos simulados.

## Configuración

`.env.example` contiene valores de ejemplo y no credenciales. Vite solo lee `VITE_API_BASE_URL`; nunca agregues credenciales a variables `VITE_*`.

## Acceso con Google y Supabase Auth

El acceso implementado usa el Authorization Code Flow con PKCE gestionado por Supabase Auth. FastAPI conserva el verificador temporal, valida el JWT y el correo verificado, devuelve el access token solo a la memoria de la aplicación y mantiene el refresh token en una cookie HttpOnly. El proveedor externo no está configurado por este repositorio; sin credenciales reales de Google/Supabase el flujo no puede completarse en vivo.

### Configuración local de Supabase

1. En Google Cloud Console, crea un cliente OAuth de tipo aplicación web. En **Authorized redirect URIs**, registra el callback que muestra Supabase en **Authentication → Providers → Google**. Para el dominio estándar tendrá la forma `https://<PROJECT_REF>.supabase.co/auth/v1/callback`; si el proyecto usa dominio de Auth personalizado, registra el callback correspondiente a ese dominio.
2. En Supabase **Authentication → Providers → Google**, habilita Google y copia allí el Client ID y Client Secret de Google Cloud. Estos valores no se guardan en este repositorio ni se deben enviar por chat.
3. En Supabase **Authentication → URL Configuration**, configura la URL del sitio como `http://localhost:5173` y permite el callback de FastAPI `http://localhost:8000/api/v1/auth/google/callback?state=*`. La lista de redirecciones de Supabase debe admitir el parámetro `state` generado por la aplicación. El backend verifica adicionalmente una cookie state de un solo uso.
4. En Supabase, habilita una clave de firma JWT asimétrica ES256 o RS256 para que el backend pueda verificar los tokens con JWKS. El verificador rechaza algoritmos simétricos y falla de forma cerrada.
5. Copia `.env.example` como `.env` en la raíz. Completa localmente `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` desde el panel del proyecto, además de `SUPABASE_AUTH_CALLBACK_URL` y `FRONTEND_AUTH_SUCCESS_URL` si cambian los puertos o dominios. No compartas el contenido de `.env`.
6. Mantén los dos orígenes como `localhost`: Vite en `http://localhost:5173` y Uvicorn en `http://localhost:8000`. Así la cookie `SameSite=Lax` permanece en el mismo sitio; CORS permite el origen frontend explícito con credenciales.

`SUPABASE_PUBLISHABLE_KEY` permanece en el backend por decisión de este proyecto. No se usa `service_role`. Las claves de Google se configuran solamente en el panel de Supabase. Ninguna de estas credenciales debe tener prefijo `VITE_`.

### Ejecución local

En una terminal PowerShell, desde la raíz (con `.env` ya configurado):

```powershell
uvicorn app.main:app --app-dir backend --env-file .env --reload --host localhost --port 8000
```

En otra terminal:

```powershell
Set-Location frontend
npm run dev -- --host localhost
```

Abre `http://localhost:5173`, selecciona **Continuar con Google** y completa el consentimiento. La callback local registrada en Supabase es `http://localhost:8000/api/v1/auth/google/callback`; el redirect URI que Google debe registrar pertenece a Supabase (`https://<PROJECT_REF>.supabase.co/auth/v1/callback`), no al callback de FastAPI.

Las transacciones OAuth se guardan en memoria de un único proceso durante 10 minutos, tienen consumo único y un límite de capacidad. Esta estrategia es solo para desarrollo local y no sirve para múltiples workers o despliegues distribuidos. El valor `AUTH_COOKIE_MAX_AGE_SECONDS` debe alinearse con la duración de sesión elegida antes de producción; producción además exige HTTPS y cookie Secure.

### Endpoints de autenticación

- `GET /api/v1/auth/google/start`: inicia Google OAuth con PKCE.
- `GET /api/v1/auth/google/callback`: valida state, intercambia el código y establece refresh cookie.
- `GET /api/v1/auth/session`: renueva la sesión mediante la cookie y devuelve access token al frontend.
- `POST /api/v1/auth/refresh`: rota la sesión y devuelve el access token renovado.
- `POST /api/v1/auth/logout`: intenta revocar la sesión en Supabase y siempre limpia la cookie local.

Los endpoints de sesión, refresh y logout validan `Origin` contra `FRONTEND_ORIGIN`. Las rutas privadas futuras pueden utilizar `app.dependencies.auth.get_current_user`, que exige JWT asimétrico válido y UUID en `sub`. No se implementan todavía perfiles, conversaciones ni rutas privadas de negocio.
