# Smart Classroom Attendance

Local-first, multi-camera classroom attendance with browser enrollment, teacher review, and student attendance analytics.

## What the system does

- Students enroll with exactly three camera captures or image uploads.
- Teachers create classes, configure multiple camera sources, and run attendance sessions.
- Each enabled camera is processed by an independent recognition worker.
- Raw sightings are retained for audit and debugging.
- Attendance is calculated using one-minute presence windows, not raw detection counts.
- Teachers can review coverage, see annotated camera feeds, and append manual corrections.
- Teacher insights include timeline replay, camera-zone summaries and health state, first/last-seen explanations, arrival/departure signals, a review queue, and downloadable CSV integrity reports.
- Students can view only their own classes and attendance history.

## Attendance model

For a 60-minute class, the system creates 60 one-minute windows. A student receives one credit for a window when at least one enabled camera confidently recognizes them during that minute.

```text
presence percentage = observed windows / eligible windows × 100
```

Example:

```text
Class duration:       60 minutes
Eligible windows:     60
Student observed:     50 windows
Presence percentage:  50 / 60 × 100 = 83.3%
```

The default automated rules are:

- `Present`: at least 70% presence and first observation within the grace period.
- `Late`: at least 70% presence but first observation after the grace period, or 30–69.9% coverage.
- `Absent`: below 30% coverage.

The current implementation uses the completed session duration to calculate eligible windows. Raw sightings from both cameras are collapsed into the same minute, so two cameras and repeated detections cannot double-count a student.

## System flow

```mermaid
flowchart LR
    A[Camera 1] --> W1[Recognition worker 1]
    B[Camera 2] --> W2[Recognition worker 2]
    C[Additional cameras] --> W3[Recognition worker N]
    W1 --> S[(Raw sightings)]
    W2 --> S
    W3 --> S
    S --> D[Minute bucket deduplication]
    D --> P[Student presence coverage]
    P --> R[Present / Late / Absent]
    R --> T[Teacher review]
    T --> O[(Append-only overrides)]
    R --> U[Student private history]
```

## Camera preview flow

The browser does not open a second connection to a webcam. The recognition worker owns each configured source and publishes its latest bounded JPEG frame through an authenticated teacher endpoint.

```mermaid
sequenceDiagram
    participant C as Camera source
    participant W as API recognition worker
    participant API as Authenticated preview API
    participant T as Teacher browser
    C->>W: Read frames continuously
    W->>W: Recognize periodically and annotate boxes/names
    W->>API: Keep latest in-memory JPEG
    T->>API: Poll selected source preview
    API-->>T: Latest annotated JPEG
```

Recognized faces are shown with green boxes and student names. Unknown faces are shown with red boxes and `Unknown`. The overlay is a visual explanation of recognition; the persisted attendance result remains the backend source of truth.

## Multi-camera behavior

- Configure two or more sources under a class.
- Each source runs independently.
- A student recognized by either camera in a minute gets one presence credit for that minute.
- A student recognized by both cameras in the same minute still gets one credit.
- If a source cannot be opened by the API machine, its preview remains unavailable and its worker contributes no sightings.
- Select any enabled source from the teacher's **Camera feed** panel during an active session.

The camera URL must be reachable from the machine running FastAPI, not only from the teacher's browser. Typical sources include webcam index `0`, an HTTP/MJPEG URL, or an RTSP URL supported by the local OpenCV build.

## Running locally

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Start the API:

```bash
cd apps/api
.venv/bin/uvicorn app.main:app --reload
```

Start the web app from the repository root:

```bash
npm run dev:web
```

Open `http://localhost:5173`.

## Project layout

```text
apps/api/       FastAPI, SQLAlchemy, recognition workers, attendance rules
apps/web/       React, TypeScript, Tailwind UI, API client
packages/       Shared contract notes
context/        Product, architecture, UI, standards, and progress docs
```

## Teacher intelligence features

Completed sessions expose a derived insights view without adding biometric data to the browser:

- **Timeline replay**: timestamped student sightings are shown in chronological order, capped to the latest 200 events.
- **Presence map / camera zones**: each configured source reports students seen and sighting volume; active sources also report healthy, degraded, or offline state based on the latest worker frame.
- **Attendance explanations**: coverage rows show first seen, last seen, camera count, and presence percentage.
- **Arrival and departure signals**: the first and last confident sightings identify late arrival and early departure review conditions.
- **Review queue**: borderline coverage, late first sightings, early departure, single-camera visibility, and no-sighting records are prioritized.
- **Integrity report**: teachers can download a CSV containing status, coverage, timing, camera count, and review reasons. It never contains embeddings, face distances, image paths, or raw media.

The API routes are teacher-owned: `GET /sessions/{session_id}/insights` and `GET /sessions/{session_id}/report.csv`.

## Privacy and access boundaries

- Students can read only their own attendance and joined classes.
- Teachers can manage only their own classes and sessions.
- Embeddings, password hashes, enrollment paths, and raw biometric media are never returned to the browser.
- Manual corrections are immutable audit events; automated attendance is never overwritten.

## Validation

```bash
npm run build:web
cd apps/api && .venv/bin/ruff check app
cd apps/api && .venv/bin/python -m compileall -q app
```
