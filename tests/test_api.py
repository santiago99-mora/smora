import os
import tempfile
import pytest
from fastapi.testclient import TestClient

# Aislar base de datos de pruebas antes de importar la app
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp_db.name}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-with-at-least-32-bytes"
os.environ["SEED_DEMO_USER"] = "false"

from main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client
    if os.path.exists(_tmp_db.name):
        try:
            os.remove(_tmp_db.name)
        except OSError:
            pass


def test_health_check(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_auth_and_task_lifecycle(client: TestClient):
    # Sin token devuelve 401
    unauth = client.get("/api/tasks")
    assert unauth.status_code == 401

    # Registro de usuario
    reg = client.post(
        "/api/auth/register",
        json={"email": "santiago@test.com", "password": "Password123"},
    )
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Registro duplicado devuelve 409
    dup = client.post(
        "/api/auth/register",
        json={"email": "santiago@test.com", "password": "Password123"},
    )
    assert dup.status_code == 409

    # Login con contraseña incorrecta devuelve 401
    bad_login = client.post(
        "/api/auth/login",
        json={"email": "santiago@test.com", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401

    # Login válido
    ok_login = client.post(
        "/api/auth/login",
        json={"email": "santiago@test.com", "password": "Password123"},
    )
    assert ok_login.status_code == 200
    assert ok_login.json()["user"]["email"] == "santiago@test.com"

    # Consultar perfil actual con token y rechazar token corrupto con 401
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "santiago@test.com"
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer invalido"}).status_code == 401

    # Crear tarea solo con title
    created = client.post(
        "/api/tasks",
        headers=headers,
        json={"title": "Comprar materiales de oficina"},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["status"] == "pendiente"

    # Listar tareas propias
    listed = client.get("/api/tasks", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    # Cambiar estado con PATCH
    patched = client.patch(
        f"/api/tasks/{task_id}/status",
        headers=headers,
        json={"status": "resuelta"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "resuelta"

    # Otro usuario no puede ver ni borrar la tarea
    other_reg = client.post(
        "/api/auth/register",
        json={"email": "otro@test.com", "password": "Password123"},
    )
    other_headers = {"Authorization": f"Bearer {other_reg.json()['access_token']}"}
    assert client.get(f"/api/tasks/{task_id}", headers=other_headers).status_code == 404
    assert client.delete(f"/api/tasks/{task_id}", headers=other_headers).status_code == 404

    # Eliminar tarea propia devuelve 204
    deleted = client.delete(f"/api/tasks/{task_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/tasks/{task_id}", headers=headers).status_code == 404
