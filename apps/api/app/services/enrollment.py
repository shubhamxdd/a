"""Biometric enrollment validation and local media persistence using InsightFace ArcFace."""

from __future__ import annotations

import shutil
import uuid

import cv2
import numpy as np
from app.config import settings
from app.services.face_engine import get_face_app
from fastapi import HTTPException, UploadFile, status

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


def create_face_encodings(student_id: uuid.UUID, photos: list[UploadFile]) -> list[tuple[str, list[float]]]:
    """Save five valid reference photos and derive a face embedding from each."""
    if len(photos) != 5:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Exactly five photos are required.")

    student_directory = settings.media_root / "enrollment" / str(student_id)
    student_directory.mkdir(parents=True, exist_ok=False)
    generated: list[tuple[str, list[float]]] = []

    face_app = get_face_app()

    try:
        for index, photo in enumerate(photos, start=1):
            if photo.content_type not in ALLOWED_CONTENT_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Photos must be JPEG or PNG images.",
                )

            suffix = ".jpg" if photo.content_type == "image/jpeg" else ".png"
            destination = student_directory / f"reference-{index}{suffix}"
            with destination.open("wb") as output:
                shutil.copyfileobj(photo.file, output)

            image = cv2.imread(str(destination))
            if image is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Photo {index} could not be read as an image.",
                )

            faces = face_app.get(image)
            if len(faces) != 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Photo {index} must contain exactly one detectable face.",
                )
            embedding: np.ndarray = faces[0].normed_embedding
            generated.append((str(destination.relative_to(settings.media_root)), embedding.tolist()))
    except Exception:
        shutil.rmtree(student_directory, ignore_errors=True)
        raise
    finally:
        for photo in photos:
            photo.file.close()

    return generated
