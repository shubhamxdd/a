"""Request and response schemas exposed by the API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models import AttendanceStatus, CameraSourceType, SessionStatus, UserRole


class TeacherRegistration(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    roll_number: str | None = None
    enrollment_complete: bool = False
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ClassroomCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    section: str | None = Field(default=None, max_length=80)


class ClassroomResponse(BaseModel):
    id: UUID
    name: str
    section: str | None
    join_code: str
    teacher_name: str
    created_at: datetime


class JoinClassRequest(BaseModel):
    join_code: str = Field(min_length=4, max_length=12)


class CameraSourceCreate(BaseModel):
    label: str = Field(min_length=2, max_length=100)
    source_type: CameraSourceType
    source: str = Field(min_length=1, max_length=2048)


class CameraSourceUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=100)
    source_type: CameraSourceType | None = None
    source: str | None = Field(default=None, min_length=1, max_length=2048)
    is_enabled: bool | None = None


class CameraSourceResponse(BaseModel):
    id: UUID
    label: str
    source_type: CameraSourceType
    source: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class AttendanceSessionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    grace_period_minutes: int = Field(default=10, ge=0, le=120)
    minimum_sightings: int = Field(default=3, ge=1, le=20)
    qualification_window_minutes: int = Field(default=5, ge=1, le=60)


class AttendanceSessionResponse(BaseModel):
    id: UUID
    class_id: UUID
    title: str
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None
    grace_period_minutes: int
    minimum_sightings: int
    qualification_window_minutes: int


class AttendanceRecordResponse(BaseModel):
    student_id: UUID
    student_name: str
    roll_number: str
    automated_status: AttendanceStatus
    qualifying_at: datetime | None


class SightingResponse(BaseModel):
    student_id: UUID
    student_name: str
    camera_source_id: UUID
    matched_at: datetime
    face_distance: float
