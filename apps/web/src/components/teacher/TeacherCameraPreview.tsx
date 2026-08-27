import { useEffect, useState } from 'react'
import { CameraOff, Circle } from 'lucide-react'
import { api, ApiError } from '../../api'
import type { CameraSource } from '../../types'
import { Panel } from '../ui/primitives'

function CameraFeed({ active, sessionId, camera }: { active: boolean; sessionId: string | null; camera: CameraSource }) {
  const [frameUrl, setFrameUrl] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    setFrameUrl('')
    setError('')
    if (!active || !sessionId) return

    let cancelled = false
    let currentUrl = ''
    let loading = false
    const loadFrame = async () => {
      if (loading) return
      loading = true
      try {
        const blob = await api.previewCamera(sessionId, camera.id)
        if (cancelled) return
        const nextUrl = URL.createObjectURL(blob)
        if (currentUrl) URL.revokeObjectURL(currentUrl)
        currentUrl = nextUrl
        setFrameUrl(nextUrl)
        setError('')
      } catch (caught) {
        if (!cancelled && caught instanceof ApiError && caught.status !== 404) setError(caught.message)
      } finally {
        loading = false
      }
    }

    void loadFrame()
    const timer = window.setInterval(() => void loadFrame(), 150)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      if (currentUrl) URL.revokeObjectURL(currentUrl)
    }
  }, [active, sessionId, camera.id])

  const sourceType = camera.source_type.replace('_', ' ')
  const waitingMessage = active
    ? `Waiting for ${camera.label}. Check that its ${sourceType} address is reachable from the API server.`
    : 'Start a session to view this camera feed.'

  return <div className="overflow-hidden rounded-lg border border-[var(--line)] bg-[#17201c]">
    <div className="flex items-center justify-between gap-3 border-b border-white/10 px-3 py-2">
      <div className="min-w-0"><p className="truncate text-sm font-bold text-white">{camera.label}</p><p className="truncate text-[10px] capitalize text-[#b8c5bc]">{sourceType} · {camera.source}</p></div>
      <span className={`flex shrink-0 items-center gap-1 text-[10px] font-bold ${frameUrl ? 'text-[#65d281]' : error ? 'text-[#ff8b8b]' : 'text-[#d6c77b]'}`}><Circle size={7} fill="currentColor" />{frameUrl ? 'Live' : error ? 'Error' : active ? 'Connecting' : 'Standby'}</span>
    </div>
    <div className="relative aspect-video">{frameUrl ? <img src={frameUrl} alt={`Live feed from ${camera.label}`} className="size-full object-contain" /> : <div className="grid size-full place-items-center p-5 text-center text-xs leading-5 text-[#b8c5bc]"><div><CameraOff size={22} className="mx-auto mb-2" />{error || waitingMessage}</div></div>}{frameUrl && <div className="absolute right-2 top-2 rounded bg-[#17201c]/75 px-2 py-1 text-[10px] text-white"><span className="text-[#65d281]">Green</span> recognized · <span className="text-[#ff8b8b]">Red</span> unknown</div>}</div>
  </div>
}

export function TeacherCameraPreview({ active, sessionId, cameras, className = '' }: { active: boolean; sessionId: string | null; cameras: CameraSource[]; className?: string }) {
  const enabledCameras = cameras.filter((camera) => camera.is_enabled)

  return <Panel title="Camera feeds" className={className} action={<span className={`flex items-center gap-1.5 text-xs font-bold ${active ? 'text-[var(--green)]' : 'text-[var(--muted)]'}`}><span className={`size-2 rounded-full ${active ? 'bg-[#35a86b]' : 'bg-[#a9b3ac]'}`} />{active ? `${enabledCameras.length} source${enabledCameras.length === 1 ? '' : 's'} live` : 'Standby'}</span>}>
    {enabledCameras.length === 0 ? <div className="grid min-h-48 place-items-center rounded-lg border border-dashed border-[var(--line)] p-5 text-center text-xs leading-5 text-[var(--muted)]">Enable a camera source to preview the feed.</div> : <div className={`grid gap-3 ${enabledCameras.length > 1 ? 'md:grid-cols-2' : ''}`}>{enabledCameras.map((camera) => <CameraFeed key={camera.id} active={active} sessionId={sessionId} camera={camera} />)}</div>}
  </Panel>
}
