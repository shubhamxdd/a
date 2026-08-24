# Progress Tracker

## Current Phase

- Phase 2 complete — ready for classroom management

## Current Goal

- Build classroom management: classes, student membership through join codes, and teacher-controlled camera settings.

## Completed

- Product scope, architecture, attendance rules, UI direction, and monorepo structure agreed.
- Context templates populated with the current specification.
- Created the monorepo workspace layout, Docker Compose PostgreSQL service, environment templates, API dependency manifests, and media-storage boundary.
- Created the isolated API virtual environment; compiled dlib 20.0.1; installed and verified FastAPI, face_recognition, and OpenCV imports.
- Added a repeatable local recognition and camera-source verification script.
- Started and verified the local PostgreSQL Docker service; it is healthy and accepting connections on port 5432.
- Verified physical laptop webcam access locally: camera index `0` opened successfully and produced a `640×480` frame.
- Implemented FastAPI configuration, PostgreSQL schema creation, CORS, and a health endpoint.
- Implemented JWT authentication, role-protected current-user resolution, teacher invite-code registration, and email/password login.
- Implemented student multipart onboarding with exactly three JPEG/PNG photos, local photo persistence, one-face-per-photo validation, and stored embeddings.
- Verified API startup, OpenAPI auth routes, health response, and Ruff static checks against the local PostgreSQL service.
- Corrected the student-upload OpenAPI schema so Swagger renders `photos` as binary file inputs rather than text strings.

## In Progress

- No implementation currently in progress.

## Next Up

- Implement Phase 3: class creation, join codes, membership APIs, and teacher camera-source configuration.

## Open Questions

- None.

## Architecture Decisions

- One Vite React application routes users by stored role.
- FastAPI owns recognition workers and REST APIs; PostgreSQL runs locally through Docker Compose.
- Enrollment photos are local files; embeddings and metadata live in PostgreSQL.

## Session Notes

- `face_recognition_models` requires `setuptools<81` because it still imports `pkg_resources`; this compatibility pin is captured in `apps/api/requirements.txt`.
- Camera sources are web-app configuration managed by teachers. OpenCV supports local indexes, IP-camera URLs, and video-file paths through the same source field.
- A live student-enrollment request still needs manual verification with three real reference images; no biometric test images were created during backend verification.
