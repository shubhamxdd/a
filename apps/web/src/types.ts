export type UserRole = 'teacher' | 'student'
export type AttendanceStatus = 'present' | 'late' | 'absent'
export type SessionStatus = 'active' | 'completed'
export type CameraSourceType = 'webcam' | 'ip_stream' | 'video_file'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  roll_number: string | null
  enrollment_complete: boolean
  created_at: string
}

export interface AuthSession {
  access_token: string
  token_type: string
  user: User
}

export interface Classroom {
  id: string
  name: string
  section: string | null
  join_code: string
  teacher_name: string
  created_at: string
}

export interface CameraSource {
  id: string
  label: string
  source_type: CameraSourceType
  source: string
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface AttendanceSession {
  id: string
  class_id: string
  title: string
  status: SessionStatus
  started_at: string
  ended_at: string | null
  grace_period_minutes: number
  minimum_sightings: number
  qualification_window_minutes: number
  presence_threshold_percentage: number
}

export interface AttendanceOverride {
  id: string
  status: AttendanceStatus
  reason: string
  teacher_id: string
  teacher_name: string
  created_at: string
}

export interface AttendanceRecord {
  student_id: string
  student_name: string
  roll_number: string
  automated_status: AttendanceStatus
  effective_status: AttendanceStatus
  qualifying_at: string | null
  observed_windows: number
  eligible_windows: number
  presence_percentage: number
  latest_override: AttendanceOverride | null
  override_history: AttendanceOverride[]
}

export interface AttendanceSummary {
  total_sessions: number
  attended_sessions: number
  present_sessions: number
  late_sessions: number
  absent_sessions: number
  attendance_percentage: number
  history: AttendanceHistoryEntry[]
}

export interface AttendanceHistoryEntry {
  session_id: string
  class_id: string
  class_name: string
  session_title: string
  session_started_at: string
  session_ended_at: string | null
  automated_status: AttendanceStatus
  effective_status: AttendanceStatus
  qualifying_at: string | null
  observed_windows: number
  eligible_windows: number
  presence_percentage: number
}

export interface Sighting {
  student_id: string
  student_name: string
  camera_source_id: string
  matched_at: string
  face_distance: number
}
