# AI-Powered Smart Classroom Attendance & Analytics System

## Overview

A local-first hackathon application for classroom attendance using a laptop webcam and a phone camera. Students self-onboard with three face photos, while teachers manage classes, camera sources, sessions, attendance corrections, and basic daily analytics.

## Goals

1. Recognize enrolled students independently from two camera feeds and merge duplicate sightings.
2. Compute Present, Late, and Absent status using transparent session rules.
3. Give teachers operational controls and students private access to only their own attendance.

## Core User Flow

1. A teacher or student creates an account from the shared login page.
2. A student supplies name, roll number, and three reference photos; embeddings are generated locally.
3. A teacher creates a class and shares its join code.
4. A student joins the class with that code.
5. The teacher configures two camera sources and starts a class session.
6. Both camera workers log qualified sightings; the system derives attendance.
7. Teachers review or override a result; students view only their own history.

## Features

### Authentication and onboarding

- One sign-in entry point with role-based routing.
- Teacher registration protected by a demo invite code.
- Student face enrollment from exactly three photos.

### Attendance

- Laptop webcam plus phone IP-stream or recorded-video source.
- Independent per-camera recognition workers and five-second cross-camera de-duplication.
- Three sightings in a rolling five-minute window qualify a student.
- Ten-minute grace period distinguishes Present from Late.

### Dashboards

- Teacher class, session, camera, attendance, and correction workflows.
- Student personal attendance percentage and session history.

## Scope

### In Scope

- Two-camera recognition, local enrollment-photo storage, PostgreSQL metadata, and basic daily analytics.
- Manual teacher attendance overrides with an audit trail.

### Out of Scope

- Engagement detection, seating maps, alerts, geometric calibration, and real multi-day trend analysis.
- Hosted deployment and production-grade identity verification.

## Success Criteria

1. A student recognized by both cameras within five seconds yields one merged sighting.
2. A teacher can complete a live session and see correct Present, Late, and Absent results.
3. A student cannot access another student's records.
