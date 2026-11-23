import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from database import Base, AsyncSessionLocal, engine, get_db
from models import TaskModel, UserModel
from schemas import (
    TaskCreate,
    TaskResponse,
    TaskStatusUpdate,
    TaskUpdate,
    TokenResponse,
    UserAuthRequest,
    UserResponse,
)

DEMO_EMAIL = os.getenv("DEMO_USER_EMAIL", "demo@gestortareas.app")
DEMO_PASSWORD = os.getenv("DEMO_USER_PASSWORD", "Demo1234!")


async def seed_demo_data() -> None:
    """Crea un usuario de prueba y tareas iniciales si aún no existen."""
    if os.getenv("SEED_DEMO_USER", "true").lower() != "true":
        return

    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(UserModel).where(UserModel.email == DEMO_EMAIL)
        )
        if existing.scalars().first() is not None:
            return

        demo_user = UserModel(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
        )
        session.add(demo_user)
        await session.flush()

        initial_tasks = [
            TaskModel(
                user_id=demo_user.id,
                title="Validar login JWT",
                description="Comprobar el guardado del token en SecureStore y manejo de 401.",
                priority="alta",
                status="pendiente",
            ),
            TaskModel(
                user_id=demo_user.id,
                title="Probar listado remoto",
                description="Verificar consumo de GET /api/tasks con encabezado Authorization.",
                priority="media",
                status="resuelta",
            ),
            TaskModel(
                user_id=demo_user.id,
                title="Generar APK preview",
                description="Compilar con EAS Build e instalar en dispositivo Android físico.",
                priority="alta",
                status="pendiente",
            ),
        ]
        session.add_all(initial_tasks)
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_demo_data()
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(
    title="Gestor de Tareas API · EDI 2026",
    description="API RESTful con autenticación JWT, bcrypt y SQLAlchemy asíncrono.",
    version="2.0.0",
    lifespan=lifespan,
)

raw_origins = os.getenv("CORS_ORIGINS", "*").strip()
allow_origins = ["*"] if raw_origins == "*" else [o.strip() for o in raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Salud"])
async def health_check():
    """Endpoint de monitoreo para verificar disponibilidad del servidor."""
    return {"status": "ok"}


@app.post(
    "/api/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Autenticación"],
)
async def register(payload: UserAuthRequest, db: AsyncSession = Depends(get_db)):
    """Registra una nueva cuenta de usuario y devuelve su JWT."""
    result = await db.execute(select(UserModel).where(UserModel.email == payload.email))
    if result.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta registrada con ese correo.",
        )

    user = UserModel(
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@app.post("/api/auth/login", response_model=TokenResponse, tags=["Autenticación"])
async def login(payload: UserAuthRequest, db: AsyncSession = Depends(get_db)):
    """Autentica por email y contraseña y devuelve un JWT Bearer."""
    result = await db.execute(select(UserModel).where(UserModel.email == payload.email))
    user = result.scalars().first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@app.get("/api/auth/me", response_model=UserResponse, tags=["Autenticación"])
async def read_current_user(current_user: UserModel = Depends(get_current_user)):
    """Devuelve la información del usuario propietario del JWT actual."""
    return current_user


async def _get_owned_task_or_404(
    task_id: int, user_id: int, db: AsyncSession
) -> TaskModel:
    result = await db.execute(
        select(TaskModel).where(
            TaskModel.id == task_id,
            TaskModel.user_id == user_id,
        )
    )
    task = result.scalars().first()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarea no encontrada.",
        )
    return task


@app.get("/api/tasks", response_model=list[TaskResponse], tags=["Tareas"])
async def list_tasks(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista las tareas del usuario autenticado ordenadas de más reciente a más antigua."""
    result = await db.execute(
        select(TaskModel)
        .where(TaskModel.user_id == current_user.id)
        .order_by(TaskModel.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


@app.post(
    "/api/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Tareas"],
)
async def create_task(
    payload: TaskCreate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Crea una nueva tarea asociada al usuario autenticado."""
    task = TaskModel(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        status="pendiente",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@app.get("/api/tasks/{task_id}", response_model=TaskResponse, tags=["Tareas"])
async def get_task(
    task_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Obtiene el detalle de una tarea específica del usuario autenticado."""
    return await _get_owned_task_or_404(task_id, current_user.id, db)


@app.put("/api/tasks/{task_id}", response_model=TaskResponse, tags=["Tareas"])
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza título, descripción, prioridad y estado de una tarea propia."""
    task = await _get_owned_task_or_404(task_id, current_user.id, db)
    task.title = payload.title
    task.description = payload.description
    task.priority = payload.priority
    task.status = payload.status
    await db.commit()
    await db.refresh(task)
    return task


@app.patch("/api/tasks/{task_id}/status", response_model=TaskResponse, tags=["Tareas"])
async def update_task_status(
    task_id: int,
    payload: TaskStatusUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza el estado ('pendiente' o 'resuelta') de una tarea propia."""
    task = await _get_owned_task_or_404(task_id, current_user.id, db)
    task.status = payload.status
    await db.commit()
    await db.refresh(task)
    return task


@app.delete(
    "/api/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Tareas"],
)
async def delete_task(
    task_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Elimina una tarea perteneciente al usuario autenticado."""
    task = await _get_owned_task_or_404(task_id, current_user.id, db)
    await db.delete(task)
    await db.commit()
    return None
