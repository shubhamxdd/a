"""Attendance qualification and result calculation."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from uuid import UUID

from app.models import (
    AttendanceRecord,
    AttendanceSession,
    AttendanceStatus,
    ClassMembership,
    Sighting,
    StudentProfile,
    User,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


def qualifying_time(session: AttendanceSession, sightings: list[Sighting]):
    """Return the first time a student reaches the rolling-window sighting threshold."""
    window = timedelta(minutes=session.qualification_window_minutes)
    timestamps = sorted(sighting.matched_at for sighting in sightings)
    for index, timestamp in enumerate(timestamps):
        window_start = timestamp - window
        count = sum(candidate >= window_start for candidate in timestamps[: index + 1])
        if count >= session.minimum_sightings:
            return timestamp
    return None


def calculate_attendance(session: AttendanceSession, db: Session) -> list[AttendanceRecord]:
    """Create one immutable automated result for each member of a completed session."""
    members = db.execute(
        select(User, StudentProfile)
        .join(ClassMembership, ClassMembership.student_id == User.id)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .where(ClassMembership.class_id == session.class_id)
    ).all()
    all_sightings = db.scalars(select(Sighting).where(Sighting.session_id == session.id)).all()
    sightings_by_student: dict[UUID, list[Sighting]] = defaultdict(list)
    for sighting in all_sightings:
        sightings_by_student[sighting.student_id].append(sighting)

    grace_deadline = session.started_at + timedelta(minutes=session.grace_period_minutes)
    records: list[AttendanceRecord] = []
    for student, _profile in members:
        qualified_at = qualifying_time(session, sightings_by_student[student.id])
        status = AttendanceStatus.ABSENT
        if qualified_at is not None:
            status = AttendanceStatus.PRESENT if qualified_at <= grace_deadline else AttendanceStatus.LATE
        record = AttendanceRecord(
            session_id=session.id,
            student_id=student.id,
            automated_status=status,
            qualifying_at=qualified_at,
        )
        db.add(record)
        records.append(record)
    db.commit()
    return records
