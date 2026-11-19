"""Crea el .env de desarrollo local a partir de .env.example.

Uso, desde la raíz del proyecto:
    python scripts/crear_env_desarrollo.py

- Genera una contraseña aleatoria para PostgreSQL y la usa en las tres variables
  que la necesitan.
- Activa el login de prueba, el administrador de prueba y el asistente con Ollama.
- Crea también frontend/.env.local con la URL del backend.
- No sobrescribe archivos existentes.
"""
from __future__ import annotations

import re
import secrets
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV, EXAMPLE = ROOT / ".env", ROOT / ".env.example"
FRONTEND_ENV = ROOT / "frontend" / ".env.local"


def main() -> int:
    if ENV.exists():
        print(f"Ya existe {ENV.name}; no se modifica. Bórralo si quieres generarlo de nuevo.")
    else:
        password = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
        text = EXAMPLE.read_text(encoding="utf-8").replace("cambia-esta-clave", password)
        values = {"DEV_LOGIN": "true", "ADMIN_EMAILS": "dev@localhost", "LLM_PROVIDER": "ollama"}
        for key, value in values.items():
            text, count = re.subn(rf"^{key}=.*$", f"{key}={value}", text, flags=re.MULTILINE)
            if count != 1:
                print(f"No se encontró {key} en .env.example.", file=sys.stderr)
                return 1
        ENV.write_text(text, encoding="utf-8")
        print(f"Creado {ENV.name}: login de prueba, administrador dev@localhost, asistente con Ollama "
              "y contraseña aleatoria de PostgreSQL.")

    if FRONTEND_ENV.exists():
        print("Ya existe frontend/.env.local; no se modifica.")
    else:
        FRONTEND_ENV.write_text("VITE_API_BASE_URL=http://localhost:8000/api/v1\n", encoding="utf-8")
        print("Creado frontend/.env.local.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
