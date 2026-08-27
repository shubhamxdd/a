"""Shared InsightFace application singleton for enrollment and recognition workers.

Loads the buffalo_l ArcFace model once and reuses it across the process.  The
detection size is configurable for recognition workers that operate on scaled
frames; enrollment always uses the full-resolution image.
"""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_face_app: Any | None = None


def get_face_app(det_size: tuple[int, int] = (640, 640)) -> Any:
    """Return a process-wide FaceAnalysis instance, creating it on first call.

    The ``det_size`` argument is applied only during the initial creation; later
    calls reuse the existing model regardless of the size passed.  Workers that
    need a specific detection size should call ``prepare`` on their own copy.
    """
    global _face_app  # noqa: PLW0603
    if _face_app is not None:
        return _face_app

    with _lock:
        if _face_app is not None:
            return _face_app

        import insightface

        app = insightface.app.FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=0, det_size=det_size)
        _face_app = app
    return _face_app


def create_worker_face_app(det_size: tuple[int, int] = (320, 320)) -> Any:
    """Create an independent FaceAnalysis instance for a recognition worker.

    Each camera worker thread gets its own instance so that per-thread state
    (such as internal buffers) does not collide.  The detection size should
    match the downscaled frame the worker feeds into the model.
    """
    import insightface

    app = insightface.app.FaceAnalysis(
        name="buffalo_l",
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=0, det_size=det_size)
    return app
