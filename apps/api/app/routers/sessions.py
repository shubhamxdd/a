"""Teacher-controlled attendance-session routes."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AttendanceOverrideEvent,
    AttendanceRecord,
    AttendanceSession,
    AttendanceStatus,
    CameraSource,
    ClassMembership,
    Classroom,
    SessionStatus,
    Sighting,
    StudentProfile,
    User,
    UserRole,
)
from app.routers.classes import get_owned_classroom
from app.schemas import (
    AttendanceOverrideCreate,
    AttendanceOverrideResponse,
    AttendanceRecordResponse,
    AttendanceSessionCreate,
    AttendanceSessionResponse,
    SightingResponse,
    StudentAttendanceEntry,
    StudentAttendanceSummary,
)
from app.security import require_role
from app.services.attendance import calculate_attendance, coverage_for_record
from app.services.recognition import recognition_manager

router = APIRouter(tags=["attendance sessions"])
DbSession = Annotated[Session, Depends(get_db)]
TeacherUser = Annotated[User, Depends(require_role(UserRole.TEACHER))]
StudentUser = Annotated[User, Depends(require_role(UserRole.STUDENT))]


def serialize_session(session: AttendanceSession) -> AttendanceSessionResponse:
    return AttendanceSessionResponse(
        id=session.id,
        class_id=session.class_id,
        title=session.title,
        status=session.status,
        started_at=session.started_at,
        ended_at=session.ended_at,
        grace_period_minutes=session.grace_period_minutes,
        minimum_sightings=session.minimum_sightings,
        qualification_window_minutes=session.qualification_window_minutes,
        presence_threshold_percentage=70.0,
    )

def serialize_override(event: AttendanceOverrideEvent, teacher: User) -> AttendanceOverrideResponse:
    return AttendanceOverrideResponse(
        id=event.id,
        status=event.corrected_status,
        reason=event.reason,
        teacher_id=teacher.id,
        teacher_name=teacher.full_name,
        created_at=event.created_at,
    )


def get_owned_session(session_id: UUID, teacher: User, db: Session) -> AttendanceSession:
    session = db.scalar(
        select(AttendanceSession)
        .join(Classroom, Classroom.id == AttendanceSession.class_id)
        .where(AttendanceSession.id == session_id, Classroom.teacher_id == teacher.id)
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance session not found.")
    return session


@router.post(
    "/classes/{class_id}/sessions",
    response_model=AttendanceSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_session(
    class_id: UUID, payload: AttendanceSessionCreate, teacher: TeacherUser, db: DbSession
) -> AttendanceSessionResponse:
    classroom = get_owned_classroom(class_id, teacher, db)
    existing = db.scalar(
        select(AttendanceSession.id).where(AttendanceSession.class_id == class_id, AttendanceSession.status == SessionStatus.ACTIVE)
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This class already has an active session.")
    enabled_camera_count = db.scalar(
        select(CameraSource.id).where(CameraSource.class_id == class_id, CameraSource.is_enabled.is_(True)).limit(1)
    )
    if enabled_camera_count is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enable at least one camera source first.")

    session = AttendanceSession(
        class_id=classroom.id,
        title=payload.title.strip(),
        started_at=datetime.now(UTC),
        grace_period_minutes=payload.grace_period_minutes,
        minimum_sightings=payload.minimum_sightings,
        qualification_window_minutes=payload.qualification_window_minutes,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    recognition_manager.start_session(session.id)
    return serialize_session(session)


@router.post("/sessions/{session_id}/stop", response_model=AttendanceSessionResponse)
def stop_session(session_id: UUID, teacher: TeacherUser, db: DbSession) -> AttendanceSessionResponse:
    session = get_owned_session(session_id, teacher, db)
    if session.status is SessionStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This session is already completed.")
    recognition_manager.stop_session(session.id)
    session.status = SessionStatus.COMPLETED
    session.ended_at = datetime.now(UTC)
    db.commit()
    db.refresh(session)
    calculate_attendance(session, db)
    return serialize_session(session)


@router.get("/classes/{class_id}/sessions", response_model=list[AttendanceSessionResponse])
def list_sessions(class_id: UUID, teacher: TeacherUser, db: DbSession) -> list[AttendanceSessionResponse]:
    get_owned_classroom(class_id, teacher, db)
    sessions = db.scalars(
        select(AttendanceSession).where(AttendanceSession.class_id == class_id).order_by(AttendanceSession.started_at.desc())
    ).all()
    return [serialize_session(session) for session in sessions]


@router.get("/sessions/{session_id}/attendance", response_model=list[AttendanceRecordResponse])
def list_attendance_records(
    session_id: UUID, teacher: TeacherUser, db: DbSession
) -> list[AttendanceRecordResponse]:
    session = get_owned_session(session_id, teacher, db)
    rows = db.execute(
        select(AttendanceRecord, User, StudentProfile)
        .join(User, User.id == AttendanceRecord.student_id)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .where(AttendanceRecord.session_id == session_id)
        .order_by(User.full_name)
    ).all()
    override_rows = db.execute(
        select(AttendanceOverrideEvent, User)
        .join(User, User.id == AttendanceOverrideEvent.teacher_id)
        .where(AttendanceOverrideEvent.session_id == session_id)
        .order_by(AttendanceOverrideEvent.created_at.desc(), AttendanceOverrideEvent.id.desc())
    ).all()
    overrides_by_student: dict[UUID, list[tuple[AttendanceOverrideEvent, User]]] = {}
    for event, override_teacher in override_rows:
        overrides_by_student.setdefault(event.student_id, []).append((event, override_teacher))

    all_sightings = db.scalars(select(Sighting).where(Sighting.session_id == session_id)).all()
    sightings_by_student: dict[UUID, list[Sighting]] = {}
    for sighting in all_sightings:
        sightings_by_student.setdefault(sighting.student_id, []).append(sighting)

    responses: list[AttendanceRecordResponse] = []
    for record, student, profile in rows:
        override_history = overrides_by_student.get(student.id, [])
        latest = override_history[0] if override_history else None
        latest_override = serialize_override(*latest) if latest else None
        observed_windows, eligible_windows, presence_percentage = coverage_for_record(
            session, sightings_by_student.get(student.id, [])
        )
        responses.append(
            AttendanceRecordResponse(
                student_id=student.id,
                student_name=student.full_name,
                roll_number=profile.roll_number,
                automated_status=record.automated_status,
                effective_status=latest[0].corrected_status if latest else record.automated_status,
                qualifying_at=record.qualifying_at,
                observed_windows=observed_windows,
                eligible_windows=eligible_windows,
                presence_percentage=presence_percentage,
                latest_override=latest_override,
                override_history=[
                    serialize_override(event, override_teacher)
                    for event, override_teacher in override_history
                ],
            )
        )
    return responses


@router.patch(
    "/sessions/{session_id}/attendance/{student_id}",
    response_model=AttendanceOverrideResponse,
    status_code=status.HTTP_201_CREATED,
)
def override_attendance(
    session_id: UUID,
    student_id: UUID,
    payload: AttendanceOverrideCreate,
    teacher: TeacherUser,
    db: DbSession,
) -> AttendanceOverrideResponse:
    """Append an immutable teacher correction without changing the automated result."""
    session = get_owned_session(session_id, teacher, db)
    if session.status is not SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance can be corrected only after the session is completed.",
        )
    attendance_record = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.student_id == student_id,
        )
    )
    if attendance_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found for this session and student.",
        )

    event = AttendanceOverrideEvent(
        session_id=session.id,
        student_id=student_id,
        teacher_id=teacher.id,
        corrected_status=payload.status,
        reason=payload.reason.strip(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return serialize_override(event, teacher)


@router.get("/sessions/{session_id}/cameras/{camera_id}/preview")
def preview_camera_frame(
    session_id: UUID, camera_id: UUID, teacher: TeacherUser, db: DbSession
) -> Response:
    session = get_owned_session(session_id, teacher, db)
    if session.status is not SessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The attendance session is not active.")
    camera = db.scalar(
        select(CameraSource).where(
            CameraSource.id == camera_id,
            CameraSource.class_id == session.class_id,
            CameraSource.is_enabled.is_(True),
        )
    )
    if camera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera source not found.")
    frame = recognition_manager.get_preview_frame(session.id, camera.id)
    if frame is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera frame is not ready.")
    return Response(content=frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/student/attendance", response_model=StudentAttendanceSummary)
def student_attendance_history(student: StudentUser, db: DbSession) -> StudentAttendanceSummary:
    """Return only this student's completed, joined-class attendance history."""
    rows = db.execute(
        select(AttendanceRecord, AttendanceSession, Classroom)
        .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
        .join(Classroom, Classroom.id == AttendanceSession.class_id)
        .join(
            ClassMembership,
            (ClassMembership.class_id == Classroom.id)
            & (ClassMembership.student_id == student.id),
        )
        .where(
            AttendanceRecord.student_id == student.id,
            AttendanceSession.status == SessionStatus.COMPLETED,
        )
        .order_by(AttendanceSession.started_at.desc())
    ).all()
    override_rows = db.execute(
        select(AttendanceOverrideEvent)
        .where(AttendanceOverrideEvent.student_id == student.id)
        .order_by(AttendanceOverrideEvent.created_at.desc(), AttendanceOverrideEvent.id.desc())
    ).scalars().all()
    latest_overrides: dict[UUID, AttendanceOverrideEvent] = {}
    for event in override_rows:
        latest_overrides.setdefault(event.session_id, event)

    history: list[StudentAttendanceEntry] = []
    for record, session, classroom in rows:
        effective_status = latest_overrides.get(record.session_id)
        observed_windows, eligible_windows, presence_percentage = coverage_for_record(
            session,
            db.scalars(
                select(Sighting).where(
                    Sighting.session_id == session.id,
                    Sighting.student_id == student.id,
                )
            ).all(),
        )
        history.append(
            StudentAttendanceEntry(
                session_id=session.id,
                class_id=classroom.id,
                class_name=classroom.name,
                session_title=session.title,
                session_started_at=session.started_at,
                session_ended_at=session.ended_at,
                automated_status=record.automated_status,
                effective_status=effective_status.corrected_status if effective_status else record.automated_status,
                qualifying_at=record.qualifying_at,
                observed_windows=observed_windows,
                eligible_windows=eligible_windows,
                presence_percentage=presence_percentage,
            )
        )

    present_sessions = sum(entry.effective_status is AttendanceStatus.PRESENT for entry in history)
    late_sessions = sum(entry.effective_status is AttendanceStatus.LATE for entry in history)
    absent_sessions = sum(entry.effective_status is AttendanceStatus.ABSENT for entry in history)
    total_sessions = len(history)
    attended_sessions = present_sessions + late_sessions
    return StudentAttendanceSummary(
        total_sessions=total_sessions,
        attended_sessions=attended_sessions,
        present_sessions=present_sessions,
        late_sessions=late_sessions,
        absent_sessions=absent_sessions,
        attendance_percentage=round(attended_sessions / total_sessions * 100, 1) if total_sessions else 0.0,
        history=history,
    )


@router.get("/sessions/{session_id}/sightings", response_model=list[SightingResponse])
def list_sightings(session_id: UUID, teacher: TeacherUser, db: DbSession) -> list[SightingResponse]:
    get_owned_session(session_id, teacher, db)
    rows = db.execute(
        select(Sighting, User)
        .join(User, User.id == Sighting.student_id)
        .where(Sighting.session_id == session_id)
        .order_by(Sighting.matched_at.desc())
    ).all()
    return [
        SightingResponse(
            student_id=user.id,
            student_name=user.full_name,
            camera_source_id=sighting.camera_source_id,
            matched_at=sighting.matched_at,
            face_distance=sighting.face_distance,
        )
        for sighting, user in rows
    ]
