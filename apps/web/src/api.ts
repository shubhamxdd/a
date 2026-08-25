import type {
  AttendanceAssistantResponse,
  AttendanceOverride,
  AttendanceRecord,
  AttendanceSession,
  AttendanceStatus,
  AttendanceSummary,
  AuthSession,
  CameraSource,
  CameraSourceType,
  Classroom,
  SessionInsights,
  Sighting,
  User,
} from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
const TOKEN_KEY = 'atten_access_token'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
  }
}

export const authStore = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setToken: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = authStore.getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  if (!response.ok) {
    let message = 'Something went wrong. Please try again.'
    try {
      const body = (await response.json()) as { detail?: string | Array<{ msg: string }> }
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((item) => item.msg).join(' ')
    } catch {
      // Keep the stable fallback message for non-JSON errors.
    }
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<T>
}

async function requestBlob(path: string): Promise<Blob> {
  const headers = new Headers()
  const token = authStore.getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_BASE_URL}${path}`, { headers, cache: 'no-store' })
  if (!response.ok) throw new ApiError(response.status === 404 ? 'Camera frame is not ready.' : 'Unable to load camera frame.', response.status)
  return response.blob()
}

export const api = {
  me: () => request<User>('/auth/me'),
  login: (email: string, password: string) =>
    request<AuthSession>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  registerTeacher: (input: { full_name: string; email: string; password: string; invite_code: string }) =>
    request<AuthSession>('/auth/register/teacher', { method: 'POST', body: JSON.stringify(input) }),
  registerStudent: (input: {
    full_name: string
    roll_number: string
    email: string
    password: string
    photos: Blob[]
  }) => {
    const body = new FormData()
    body.set('full_name', input.full_name)
    body.set('roll_number', input.roll_number)
    body.set('email', input.email)
    body.set('password', input.password)
    input.photos.forEach((photo, index) => body.append('photos', photo, `capture-${index + 1}.jpg`))
    return request<AuthSession>('/auth/register/student', { method: 'POST', body })
  },
  listClasses: () => request<Classroom[]>('/classes'),
  createClass: (name: string, section: string) =>
    request<Classroom>('/classes', { method: 'POST', body: JSON.stringify({ name, section: section || null }) }),
  joinClass: (join_code: string) =>
    request<Classroom>('/classes/join', { method: 'POST', body: JSON.stringify({ join_code }) }),
  listCameras: (classId: string) => request<CameraSource[]>(`/classes/${classId}/camera-sources`),
  createCamera: (classId: string, input: { label: string; source_type: CameraSourceType; source: string }) =>
    request<CameraSource>(`/classes/${classId}/camera-sources`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  updateCamera: (classId: string, cameraId: string, input: Partial<Pick<CameraSource, 'label' | 'source_type' | 'source' | 'is_enabled'>>) =>
    request<CameraSource>(`/classes/${classId}/camera-sources/${cameraId}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    }),
  deleteCamera: (classId: string, cameraId: string) =>
    request<void>(`/classes/${classId}/camera-sources/${cameraId}`, { method: 'DELETE' }),
  listSessions: (classId: string) => request<AttendanceSession[]>(`/classes/${classId}/sessions`),
  startSession: (classId: string, input: { title: string; qualification_window_minutes: number; grace_period_minutes: number }) =>
    request<AttendanceSession>(`/classes/${classId}/sessions`, {
      method: 'POST',
      body: JSON.stringify({ ...input, minimum_sightings: 1 }),
    }),
  stopSession: (sessionId: string) =>
    request<AttendanceSession>(`/sessions/${sessionId}/stop`, { method: 'POST' }),
  listAttendance: (sessionId: string) =>
    request<AttendanceRecord[]>(`/sessions/${sessionId}/attendance`),
  previewCamera: (sessionId: string, cameraId: string) =>
    requestBlob(`/sessions/${sessionId}/cameras/${cameraId}/preview`),
  listSightings: (sessionId: string) => request<Sighting[]>(`/sessions/${sessionId}/sightings`),
  assignUnknownSighting: (sessionId: string, sightingId: string, studentId: string) =>
    request(`/sessions/${sessionId}/sightings/${sightingId}/assign/${studentId}`, { method: 'POST' }),
  sessionInsights: (sessionId: string) => request<SessionInsights>(`/sessions/${sessionId}/insights`),
  downloadReport: (sessionId: string) => requestBlob(`/sessions/${sessionId}/report.csv`),
  studentAttendance: () => request<AttendanceSummary>('/student/attendance'),
  teacherAttendanceAssistant: (query: string, classId?: string) =>
    request<AttendanceAssistantResponse>('/teacher/attendance-assistant', {
      method: 'POST',
      body: JSON.stringify({ query, class_id: classId || null }),
    }),
  overrideAttendance: (sessionId: string, studentId: string, status: AttendanceStatus, reason: string) =>
    request<AttendanceOverride>(`/sessions/${sessionId}/attendance/${studentId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status, reason }),
    }),
}
