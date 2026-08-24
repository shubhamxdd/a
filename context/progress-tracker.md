# Progress Tracker

## Current Phase

- Phase 4 complete — ready for React web application scaffolding

## Current Goal

- Scaffold the React web application and implement the shared authentication/onboarding shell.

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
- Implemented attendance-session, sighting, and automated attendance-record persistence.
- Implemented one independent OpenCV/face-recognition worker per enabled camera source, sampled once per second with a face-distance threshold below `0.5`.
- Implemented five-second cross-camera (not same-camera) de-duplication and final Present/Late/Absent calculation using the agreed rolling five-minute, three-sighting rule.
- Added a teacher-only live-sightings endpoint for recognition verification before a session ends.
- Added an OpenCV camera-preview utility to visually validate webcam, IP-stream, and video-file sources outside the attendance worker.
- Added a disposable end-to-end demo setup and annotated live-recognition preview script using `student.jpg` as three enrollment references.
- Updated the demo setup script to generate validator-compatible demo email addresses and expose API validation details when setup fails.
- Decided that the React student onboarding flow will capture three photos directly from the browser camera; API file upload remains a fallback and test interface.
- Verified session API table creation and routes, Ruff checks, and deterministic attendance qualification logic.
- Manually verified Phase 4 live recognition and attendance workers with enrolled reference images and a camera source.

## In Progress

- No implementation currently in progress.

## Next Up

- Scaffold the Vite, React, TypeScript, and Tailwind web application.
- Implement the shared authentication flow and role-based routing.
- Implement browser-camera capture of exactly three student enrollment photos.

## Open Questions

- None.

## Architecture Decisions

- One Vite React application routes users by stored role.
- FastAPI owns recognition workers and REST APIs; PostgreSQL runs locally through Docker Compose.
- Enrollment photos are local files; embeddings and metadata live in PostgreSQL.

## Session Notes

- `face_recognition_models` requires `setuptools<81` because it still imports `pkg_resources`; this compatibility pin is captured in `apps/api/requirements.txt`.
- Camera sources are web-app configuration managed by teachers. OpenCV supports local indexes, IP-camera URLs, and video-file paths through the same source field.
- Live student enrollment and recognition have been manually verified with real reference images and a camera source; local biometric media remains untracked and must not be committed.
- Start a session only after a class has at least one enabled camera source; recognition workers run inside the FastAPI process and stop when the session stops or the API shuts down.
