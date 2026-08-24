# Architecture Context

## Stack

| Layer | Technology | Role |
| --- | --- | --- |
| Web | Vite, React, TypeScript, Tailwind CSS, browser `getUserMedia` | Role-based interface and guided enrollment-photo capture |
| API | FastAPI, SQLAlchemy | REST API, authentication, session orchestration |
| Recognition | Python, face_recognition, OpenCV | Enrollment encoding and independent camera workers |
| Database | PostgreSQL via Docker Compose | Users, classes, sessions, sightings, attendance, audit events |
| Media | Local `apps/api/storage/` | Enrollment photo files |

## System Boundaries

- `apps/web/` owns browser UI and API consumption only.
- `apps/api/` owns authentication, persistence, recognition, attendance rules, camera workers, and bounded live preview frames.
- Teacher camera previews reuse the recognition worker's latest JPEG frame through a teacher-authenticated endpoint; they never open the configured camera a second time.
- `packages/contracts/` owns shared API contract documentation and types.
- `context/` owns the current product and engineering specification.

## Storage Model

- **PostgreSQL**: user profiles, password hashes, classes, memberships, face-encoding metadata, camera settings, sessions, raw sightings, computed attendance, and override audit events.
- **Local media storage**: the three uploaded enrollment photos per student. Database rows retain safe relative paths.

## Auth and Access Model

- Every request is authenticated by a local account token.
- A stored user role determines teacher or student UI and API access.
- Teacher registration requires a configured demo invite code.
- Students may read only their own profile, memberships, and attendance. Teachers may manage only their own classes and sessions.

## Invariants

1. Camera workers are independent and communicate only through persisted sightings.
2. Raw automated attendance is never overwritten by a teacher correction; corrections create immutable audit events.
3. A match at face distance `>= 0.5` cannot create a student sighting.
4. Enrollment images remain local and embeddings are generated before a student can participate in attendance.
5. Live preview storage is bounded to one in-memory compressed frame per active camera and is removed when its session stops.
