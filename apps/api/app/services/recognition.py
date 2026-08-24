"""Independent OpenCV/face-recognition workers backed by persisted sightings."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import cv2
import face_recognition
import numpy as np
from app.database import SessionLocal
from app.models import (
    AttendanceSession,
    CameraSource,
    CameraSourceType,
    ClassMembership,
    FaceEncoding,
    SessionStatus,
    Sighting,
)
from sqlalchemy import select

MATCH_DISTANCE = 0.5
SAMPLE_INTERVAL_SECONDS = 1.0
DEDUPLICATION_WINDOW = timedelta(seconds=5)


@dataclass
class WorkerHandle:
    stop_event: threading.Event
    thread: threading.Thread


def parse_capture_source(source_type: CameraSourceType, source: str) -> int | str:
    return int(source) if source_type is CameraSourceType.WEBCAM and source.isdigit() else source


def log_sighting(session_id: UUID, student_id: UUID, camera_id: UUID, distance: float) -> None:
    """Persist a match unless another camera already logged it in the five-second merge window."""
    matched_at = datetime.now(UTC)
    with SessionLocal() as db:
        session = db.get(AttendanceSession, session_id)
        if session is None or session.status is not SessionStatus.ACTIVE:
            return
        duplicate = db.scalar(
            select(Sighting.id)
            .where(
                Sighting.session_id == session_id,
                Sighting.student_id == student_id,
                Sighting.camera_source_id != camera_id,
                Sighting.matched_at >= matched_at - DEDUPLICATION_WINDOW,
            )
            .limit(1)
        )
        if duplicate is None:
            db.add(
                Sighting(
                    session_id=session_id,
                    student_id=student_id,
                    camera_source_id=camera_id,
                    matched_at=matched_at,
                    face_distance=distance,
                )
            )
            db.commit()


def run_worker(
    session_id: UUID,
    camera: CameraSource,
    known_student_ids: list[UUID],
    known_embeddings: list[list[float]],
    stop_event: threading.Event,
) -> None:
    """Read one camera source and independently log confident student matches."""
    capture = cv2.VideoCapture(parse_capture_source(camera.source_type, camera.source))
    known_vectors = np.array(known_embeddings)
    try:
        while not stop_event.is_set():
            read_ok, frame = capture.read()
            if not read_ok:
                if camera.source_type is CameraSourceType.VIDEO_FILE:
                    break
                stop_event.wait(0.5)
                continue

            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            locations = face_recognition.face_locations(rgb_frame)
            encodings = face_recognition.face_encodings(rgb_frame, locations)
            for encoding in encodings:
                distances = face_recognition.face_distance(known_vectors, encoding)
                if distances.size == 0:
                    continue
                match_index = int(np.argmin(distances))
                distance = float(distances[match_index])
                if distance < MATCH_DISTANCE:
                    log_sighting(session_id, known_student_ids[match_index], camera.id, distance)
            stop_event.wait(SAMPLE_INTERVAL_SECONDS)
    finally:
        capture.release()


class RecognitionManager:
    """Owns process-local worker threads for active attendance sessions."""

    def __init__(self) -> None:
        self._workers: dict[UUID, list[WorkerHandle]] = {}
        self._lock = threading.Lock()

    def start_session(self, session_id: UUID) -> int:
        with self._lock, SessionLocal() as db:
            session = db.get(AttendanceSession, session_id)
            if session is None:
                return 0
            sources = db.scalars(
                select(CameraSource).where(CameraSource.class_id == session.class_id, CameraSource.is_enabled.is_(True))
            ).all()
            enrolled = db.execute(
                select(FaceEncoding.student_id, FaceEncoding.embedding)
                .join(ClassMembership, ClassMembership.student_id == FaceEncoding.student_id)
                .where(ClassMembership.class_id == session.class_id)
            ).all()
            student_ids = [student_id for student_id, _embedding in enrolled]
            embeddings = [embedding for _student_id, embedding in enrolled]
            handles: list[WorkerHandle] = []
            for camera in sources:
                stop_event = threading.Event()
                thread = threading.Thread(
                    target=run_worker,
                    args=(session_id, camera, student_ids, embeddings, stop_event),
                    daemon=True,
                    name=f"recognition-{session_id}-{camera.id}",
                )
                thread.start()
                handles.append(WorkerHandle(stop_event=stop_event, thread=thread))
            self._workers[session_id] = handles
            return len(handles)

    def stop_session(self, session_id: UUID) -> None:
        with self._lock:
            handles = self._workers.pop(session_id, [])
        for handle in handles:
            handle.stop_event.set()
        for handle in handles:
            handle.thread.join(timeout=3)

    def stop_all(self) -> None:
        for session_id in list(self._workers):
            self.stop_session(session_id)


recognition_manager = RecognitionManager()
