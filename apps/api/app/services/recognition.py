"""Independent OpenCV/InsightFace ArcFace workers backed by persisted sightings."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID

import cv2
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
    User,
)
from app.services.face_engine import create_worker_face_app
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Cosine similarity threshold — a match must be >= this value (higher is better).
# With dlib/face_recognition, the invariant was distance < 0.5 (lower is better).
# ArcFace normed embeddings yield cosine similarity in [−1, 1]; practical matches
# fall in [0.2, 1.0].  A threshold of 0.5 rejects weak and false positives while
# accepting confident same-person matches.
MATCH_SIMILARITY = 0.5
ARCFACE_EMBEDDING_DIMENSION = 512
SAMPLE_INTERVAL_SECONDS = 15.0
PREVIEW_WIDTH = 640
UNKNOWN_EVENT_INTERVAL = timedelta(seconds=5)
DEDUPLICATION_WINDOW = timedelta(seconds=5)


@dataclass
class WorkerHandle:
    camera_id: UUID
    stop_event: threading.Event
    thread: threading.Thread


@dataclass
class CameraHealth:
    last_frame_at: datetime | None = None
    last_attempt_at: datetime | None = None
    status: str = "starting"
    error: str | None = None


def parse_capture_source(source_type: CameraSourceType, source: str) -> int | str:
    return int(source) if source_type is CameraSourceType.WEBCAM and source.isdigit() else source


def prepare_known_faces(
    student_ids: list[UUID],
    student_names: list[str],
    embeddings: list[list[float]],
) -> tuple[list[UUID], list[str], np.ndarray]:
    """Keep valid ArcFace vectors while preserving student/name alignment."""
    valid_ids: list[UUID] = []
    valid_names: list[str] = []
    valid_vectors: list[np.ndarray] = []
    for student_id, student_name, embedding in zip(student_ids, student_names, embeddings, strict=True):
        try:
            vector = np.asarray(embedding, dtype=np.float32)
        except (TypeError, ValueError):
            logger.warning("Ignoring malformed face embedding for student=%s", student_id)
            continue
        if vector.shape != (ARCFACE_EMBEDDING_DIMENSION,) or not np.all(np.isfinite(vector)):
            logger.warning(
                "Ignoring incompatible face embedding for student=%s: expected=%s actual=%s",
                student_id,
                ARCFACE_EMBEDDING_DIMENSION,
                vector.size,
            )
            continue
        norm = float(np.linalg.norm(vector))
        if norm == 0:
            logger.warning("Ignoring zero-length face embedding for student=%s", student_id)
            continue
        valid_ids.append(student_id)
        valid_names.append(student_name)
        valid_vectors.append(vector / norm)
    vectors = (
        np.stack(valid_vectors)
        if valid_vectors
        else np.empty((0, ARCFACE_EMBEDDING_DIMENSION), dtype=np.float32)
    )
    return valid_ids, valid_names, vectors


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


def log_unknown_sighting(session_id: UUID, camera_id: UUID) -> None:
    """Persist at most one anonymous event per camera every five seconds."""
    matched_at = datetime.now(UTC)
    with SessionLocal() as db:
        session = db.get(AttendanceSession, session_id)
        if session is None or session.status is not SessionStatus.ACTIVE:
            return
        recent_unknown = db.scalar(
            select(Sighting.id)
            .where(
                Sighting.session_id == session_id,
                Sighting.student_id.is_(None),
                Sighting.camera_source_id == camera_id,
                Sighting.matched_at >= matched_at - UNKNOWN_EVENT_INTERVAL,
            )
            .limit(1)
        )
        if recent_unknown is None:
            db.add(
                Sighting(
                    session_id=session_id,
                    student_id=None,
                    camera_source_id=camera_id,
                    matched_at=matched_at,
                    face_distance=None,
                )
            )
            db.commit()


def run_worker(
    session_id: UUID,
    camera: CameraSource,
    known_student_ids: list[UUID],
    known_student_names: list[str],
    known_embeddings: list[list[float]],
    stop_event: threading.Event,
    sample_interval_seconds: float = SAMPLE_INTERVAL_SECONDS,
) -> None:
    """Read one camera source and independently log confident student matches."""
    known_student_ids, known_student_names, known_vectors = prepare_known_faces(
        known_student_ids,
        known_student_names,
        known_embeddings,
    )
    if known_embeddings and not known_vectors.size:
        logger.error(
            "No compatible ArcFace embeddings are available for session=%s; camera preview will continue but all faces will be unknown.",
            session_id,
        )

    last_processed_at = 0.0
    last_preview_at = 0.0
    annotations: list[tuple[int, int, int, int, str, tuple[int, int, int]]] = []

    # Each worker thread gets its own InsightFace instance for thread safety.
    try:
        face_app = create_worker_face_app(det_size=(320, 320))
    except Exception as error:
        message = f"Recognition engine unavailable: {error}"
        logger.exception("Camera worker failed to initialize: camera=%s source=%s", camera.id, camera.source)
        recognition_manager.mark_camera_error(session_id, camera.id, message)
        return

    capture = cv2.VideoCapture(parse_capture_source(camera.source_type, camera.source))
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not capture.isOpened():
        message = f"Camera source could not be opened: {camera.source}"
        logger.error("Camera worker could not open source: camera=%s type=%s source=%s", camera.id, camera.source_type.value, camera.source)
        recognition_manager.mark_camera_error(session_id, camera.id, message)
        capture.release()
        return

    try:
        while not stop_event.is_set():
            read_ok, frame = capture.read()
            if not read_ok:
                recognition_manager.mark_camera_attempt(session_id, camera.id, successful=False)
                if camera.source_type is CameraSourceType.VIDEO_FILE:
                    break
                stop_event.wait(0.1)
                continue

            recognition_manager.mark_camera_attempt(session_id, camera.id, successful=True)
            now = monotonic()
            if now - last_processed_at >= sample_interval_seconds:
                last_processed_at = now
                annotations = []
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                faces = face_app.get(small_frame)
                for face in faces:
                    bbox = face.bbox.astype(int)
                    # Scale bounding box coordinates back to original frame size
                    left, top, right, bottom = (int(v * 4) for v in bbox)
                    label = "Unknown"
                    color = (80, 80, 220)
                    matched = False

                    embedding = face.normed_embedding.astype(np.float32)
                    if known_vectors.size:
                        # Cosine similarity via dot product; both vectors are normalized.
                        similarities = known_vectors @ embedding
                        match_index = int(np.argmax(similarities))
                        similarity = float(similarities[match_index])
                        if similarity >= MATCH_SIMILARITY:
                            matched = True
                            label = known_student_names[match_index]
                            color = (70, 180, 90)
                            log_sighting(session_id, known_student_ids[match_index], camera.id, similarity)
                    if not matched:
                        log_unknown_sighting(session_id, camera.id)
                    annotations.append((top, right, bottom, left, label, color))

            if now - last_preview_at >= 0.1:
                last_preview_at = now
                for top, right, bottom, left, label, color in annotations:
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    cv2.rectangle(frame, (left, max(0, bottom - 30)), (right, bottom), color, cv2.FILLED)
                    cv2.putText(
                        frame,
                        label,
                        (left + 6, bottom - 9),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (255, 255, 255),
                        1,
                        cv2.LINE_AA,
                    )
                preview = frame
                if frame.shape[1] > PREVIEW_WIDTH:
                    preview = cv2.resize(
                        frame,
                        (PREVIEW_WIDTH, int(frame.shape[0] * PREVIEW_WIDTH / frame.shape[1])),
                    )
                recognition_manager.publish_frame(session_id, camera.id, preview)
    except Exception as error:
        message = f"Camera worker stopped unexpectedly: {error}"
        logger.exception("Camera worker crashed: camera=%s source=%s", camera.id, camera.source)
        recognition_manager.mark_camera_error(session_id, camera.id, message)
    finally:
        capture.release()


class RecognitionManager:
    """Owns process-local worker threads for active attendance sessions."""

    def __init__(self) -> None:
        self._workers: dict[UUID, list[WorkerHandle]] = {}
        self._preview_frames: dict[tuple[UUID, UUID], bytes] = {}
        self._camera_health: dict[tuple[UUID, UUID], CameraHealth] = {}
        self._lock = threading.Lock()

    def mark_camera_attempt(self, session_id: UUID, camera_id: UUID, successful: bool) -> None:
        with self._lock:
            health = self._camera_health.setdefault((session_id, camera_id), CameraHealth())
            now = datetime.now(UTC)
            health.last_attempt_at = now
            if successful:
                health.last_frame_at = now
                health.status = "healthy"
            elif health.last_frame_at is None or (now - health.last_frame_at).total_seconds() > 5:
                health.status = "offline"

    def mark_camera_error(self, session_id: UUID, camera_id: UUID, error: str) -> None:
        with self._lock:
            health = self._camera_health.setdefault((session_id, camera_id), CameraHealth())
            health.status = "error"
            health.error = error
            health.last_attempt_at = datetime.now(UTC)

    def get_camera_health(self, session_id: UUID, camera_id: UUID) -> CameraHealth:
        with self._lock:
            health = self._camera_health.get((session_id, camera_id))
            if health is None:
                return CameraHealth(status="offline")
            if health.last_frame_at and (datetime.now(UTC) - health.last_frame_at).total_seconds() > 5:
                health.status = "degraded"
            return CameraHealth(health.last_frame_at, health.last_attempt_at, health.status, health.error)

    def publish_frame(self, session_id: UUID, camera_id: UUID, frame: np.ndarray) -> None:
        """Keep one bounded JPEG preview per worker without retaining raw frame history."""
        encoded, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
        if encoded:
            with self._lock:
                self._preview_frames[(session_id, camera_id)] = buffer.tobytes()

    def get_preview_frame(self, session_id: UUID, camera_id: UUID) -> bytes | None:
        with self._lock:
            return self._preview_frames.get((session_id, camera_id))

    def start_session(self, session_id: UUID) -> int:
        with self._lock, SessionLocal() as db:
            session = db.get(AttendanceSession, session_id)
            if session is None:
                return 0
            sources = db.scalars(
                select(CameraSource).where(
                    CameraSource.room_id == session.room_id,
                    CameraSource.is_enabled.is_(True),
                )
            ).all()
            enrolled = db.execute(
                select(FaceEncoding.student_id, User.full_name, FaceEncoding.embedding)
                .join(User, User.id == FaceEncoding.student_id)
                .join(ClassMembership, ClassMembership.student_id == FaceEncoding.student_id)
                .where(ClassMembership.class_id == session.class_id)
            ).all()
            student_ids = [student_id for student_id, _name, _embedding in enrolled]
            student_names = [name for _student_id, name, _embedding in enrolled]
            embeddings = [embedding for _student_id, _name, embedding in enrolled]
            sample_interval = max(15.0, float(session.qualification_window_minutes) * 60.0) if session and session.qualification_window_minutes else SAMPLE_INTERVAL_SECONDS
            handles: list[WorkerHandle] = []
            for camera in sources:
                self._camera_health[(session_id, camera.id)] = CameraHealth()
            for camera in sources:
                stop_event = threading.Event()
                thread = threading.Thread(
                    target=run_worker,
                    args=(session_id, camera, student_ids, student_names, embeddings, stop_event, sample_interval),
                    daemon=True,
                    name=f"recognition-{session_id}-{camera.id}",
                )
                thread.start()
                handles.append(WorkerHandle(camera_id=camera.id, stop_event=stop_event, thread=thread))
            self._workers[session_id] = handles
            return len(handles)

    def stop_session(self, session_id: UUID) -> None:
        with self._lock:
            handles = self._workers.pop(session_id, [])
        for handle in handles:
            handle.stop_event.set()
        for handle in handles:
            handle.thread.join(timeout=3)
        with self._lock:
            for handle in handles:
                self._preview_frames.pop((session_id, handle.camera_id), None)
                self._camera_health.pop((session_id, handle.camera_id), None)

    def stop_all(self) -> None:
        for session_id in list(self._workers):
            self.stop_session(session_id)


recognition_manager = RecognitionManager()
