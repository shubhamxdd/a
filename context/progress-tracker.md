# Progress Tracker

## Current Phase

- Phase 3 implemented — ready for manual API testing

## Current Goal

- Manually verify classroom creation, class-code membership, and teacher-controlled camera settings.

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
- Implemented teacher-owned classes, unique join codes, student class memberships, and role-aware class listing.
- Implemented teacher-only camera-source create, list, and update APIs supporting webcam indexes, IP-camera URLs, and video-file paths.
- Verified the new ORM mappings, database table creation, API startup, OpenAPI class routes, and Ruff checks against PostgreSQL.

## In Progress

- Manual Phase 3 API verification in Swagger or curl.

## Next Up

- After manual verification, commit Phase 3 and implement attendance sessions plus camera workers.

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
