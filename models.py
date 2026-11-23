from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


def utc_now() -> datetime:
    """Devuelve la fecha/hora actual en UTC."""
    return datetime.now(timezone.utc)


class UserModel(Base):
    """Usuario registrado para autenticación JWT."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    tasks: Mapped[list["TaskModel"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class TaskModel(Base):
    """Tarea perteneciente a un usuario autenticado."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="media", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pendiente", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    owner: Mapped[UserModel] = relationship(back_populates="tasks")
