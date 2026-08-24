"""Time-window attendance coverage and result calculation."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AttendanceRecord,
    AttendanceSession,
    AttendanceStatus,
    ClassMembership,
    Sighting,
    StudentProfile,
    User,
)

PRESENT_THRESHOLD_PERCENTAGE = 70.0
LATE_THRESHOLD_PERCENTAGE = 30.0


def session_window_count(session: AttendanceSession) -> int:
    """Return the number of one-minute windows available in a completed session."""
    if session.ended_at is None:
        return 0
    duration_seconds = max(60.0, (session.ended_at - session.started_at).total_seconds())
    return max(1, math.ceil(duration_seconds / 60))


def observed_window_indexes(session: AttendanceSession, sightings: list[Sighting]) -> set[int]:
    """Collapse any number of camera sightings into one minute-level observation."""
    total_windows = session_window_count(session)
    indexes: set[int] = set()
    for sighting in sightings:
        offset_seconds = (sighting.matched_at - session.started_at).total_seconds()
        if offset_seconds < 0:
            continue
        window_index = int(offset_seconds // 60)
        if window_index < total_windows:
            indexes.add(window_index)
    return indexes


def calculate_attendance(session: AttendanceSession, db: Session) -> list[AttendanceRecord]:
    """Create one automated result per member using one-minute presence coverage."""
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

    eligible_windows = session_window_count(session)
    grace_deadline = session.started_at + timedelta(minutes=session.grace_period_minutes)
    records: list[AttendanceRecord] = []
    for student, _profile in members:
        sightings = sightings_by_student[student.id]
        observed_indexes = observed_window_indexes(session, sightings)
        observed_windows = len(observed_indexes)
        percentage = observed_windows / eligible_windows * 100 if eligible_windows else 0.0
        qualifying_at = min(
            (sighting.matched_at for sighting in sightings),
            default=None,
        )
        if percentage >= PRESENT_THRESHOLD_PERCENTAGE:
            status = AttendanceStatus.PRESENT if qualifying_at and qualifying_at <= grace_deadline else AttendanceStatus.LATE
        elif percentage >= LATE_THRESHOLD_PERCENTAGE:
            status = AttendanceStatus.LATE
        else:
            status = AttendanceStatus.ABSENT
        record = AttendanceRecord(
            session_id=session.id,
            student_id=student.id,
            automated_status=status,
            qualifying_at=qualifying_at,
        )
        db.add(record)
        records.append(record)
    db.commit()
    return records


def coverage_for_record(
    session: AttendanceSession, sightings: list[Sighting]
) -> tuple[int, int, float]:
    """Return observed windows, eligible windows, and percentage for API serialization."""
    eligible_windows = session_window_count(session)
    observed_windows = len(observed_window_indexes(session, sightings))
    percentage = observed_windows / eligible_windows * 100 if eligible_windows else 0.0
    return observed_windows, eligible_windows, round(percentage, 1)
