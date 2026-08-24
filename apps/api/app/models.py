"""Persistence models for accounts and biometric enrollment."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    TEACHER = "teacher"
    STUDENT = "student"


class CameraSourceType(str, enum.Enum):
    WEBCAM = "webcam"
    IP_STREAM = "ip_stream"
    VIDEO_FILE = "video_file"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"))
    full_name: Mapped[str] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student_profile: Mapped[StudentProfile | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    face_encodings: Mapped[list[FaceEncoding]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    taught_classes: Mapped[list[Classroom]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )
    class_memberships: Mapped[list[ClassMembership]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    roll_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    enrollment_complete: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="student_profile")


class FaceEncoding(Base):
    __tablename__ = "face_encodings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    image_path: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped[User] = relationship(back_populates="face_encodings")


class Classroom(Base):
    __tablename__ = "classes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    section: Mapped[str | None] = mapped_column(String(80), nullable=True)
    join_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    teacher: Mapped[User] = relationship(back_populates="taught_classes")
    memberships: Mapped[list[ClassMembership]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )
    camera_sources: Mapped[list[CameraSource]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )


class ClassMembership(Base):
    __tablename__ = "class_memberships"
    __table_args__ = (UniqueConstraint("class_id", "student_id", name="uq_class_membership"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    classroom: Mapped[Classroom] = relationship(back_populates="memberships")
    student: Mapped[User] = relationship(back_populates="class_memberships")


class CameraSource(Base):
    __tablename__ = "camera_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    source_type: Mapped[CameraSourceType] = mapped_column(
        Enum(CameraSourceType, name="camera_source_type")
    )
    source: Mapped[str] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    classroom: Mapped[Classroom] = relationship(back_populates="camera_sources")
