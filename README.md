# Gestor de Tareas · Backend API (FastAPI + SQLAlchemy 2.0 + JWT)

API RESTful desacoplada para autenticación con JWT (`bcrypt`) y gestión de tareas por usuario.

## Stack
- Python 3.11+ / FastAPI
- SQLAlchemy 2.0 asíncrono (`sqlite+aiosqlite` en local, compatible con PostgreSQL vía `DATABASE_URL`)
- PyJWT + bcrypt
- Pytest + HTTPX

## Levantar en local
```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Documentación interactiva Swagger disponible en `http://localhost:8000/docs`.

## Usuario de prueba inicial
Si `SEED_DEMO_USER=true`, al iniciar la base vacía se crea automáticamente:
- **Email:** `demo@gestortareas.app`
- **Password:** `Demo1234!`

## Endpoints principales
| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `GET` | `/health` | No | Verificación de disponibilidad |
| `POST` | `/api/auth/register` | No | Registro de usuario + JWT |
| `POST` | `/api/auth/login` | No | Login + JWT (`401` si falla) |
| `GET` | `/api/auth/me` | Bearer | Usuario autenticado actual |
| `GET` | `/api/tasks` | Bearer | Listar tareas del usuario |
| `POST` | `/api/tasks` | Bearer | Crear tarea (`title`, `description?`, `priority?`) |
| `GET` | `/api/tasks/{id}` | Bearer | Detalle de tarea propia |
| `PUT` | `/api/tasks/{id}` | Bearer | Editar tarea propia |
| `PATCH` | `/api/tasks/{id}/status` | Bearer | Cambiar estado (`pendiente` / `resuelta`) |
| `DELETE` | `/api/tasks/{id}` | Bearer | Eliminar tarea propia (`204`) |

## Pruebas
```bash
pytest -v
```
