from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

TaskStatus = Literal["pendiente", "resuelta"]
TaskPriority = Literal["alta", "media", "baja"]


class UserAuthRequest(BaseModel):
    """Payload compartido para registro y login."""

    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserResponse(BaseModel):
    """Datos públicos de la cuenta autenticada."""

    id: int
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Respuesta estándar de autenticación JWT."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TaskCreate(BaseModel):
    """Esquema para crear una nueva tarea."""

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    priority: TaskPriority = "media"

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El título no puede estar vacío.")
        return cleaned

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class TaskUpdate(TaskCreate):
    """Esquema para editar campos de una tarea existente."""

    status: TaskStatus = "pendiente"


class TaskStatusUpdate(BaseModel):
    """Esquema para actualizar únicamente el estado de una tarea."""

    status: TaskStatus


class TaskResponse(BaseModel):
    """Representación serializada de una tarea en respuestas REST."""

    id: int
    user_id: int
    title: str
    description: str | None = None
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
