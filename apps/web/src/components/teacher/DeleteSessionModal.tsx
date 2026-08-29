import { useState } from 'react'
import { api } from '../../api'
import type { AttendanceSession } from '../../types'
import { Modal, Notice } from '../ui/primitives'

export function DeleteSessionModal({ session, onClose, onDeleted }: { session: AttendanceSession; onClose: () => void; onDeleted: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const confirmDelete = async () => {
    setBusy(true)
    setError('')
    try {
      await api.deleteSession(session.id)
      onDeleted()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to delete this session.')
      setBusy(false)
    }
  }

  return (
    <Modal title="Delete session" onClose={onClose}>
      <p className="text-sm leading-6 text-[var(--muted)]">
        This permanently deletes <strong className="text-[var(--ink)]">{session.title}</strong> and all its sightings, attendance records, and override history. This cannot be undone.
      </p>
      {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}
      <div className="mt-6 flex gap-3">
        <button onClick={onClose} disabled={busy} className="flex-1 rounded-md border border-[var(--line)] py-3 text-sm font-bold text-[var(--ink)] hover:bg-[#f5f7f4] disabled:opacity-50">Cancel</button>
        <button onClick={confirmDelete} disabled={busy} className="flex-1 rounded-md bg-[var(--red)] py-3 text-sm font-bold text-white disabled:opacity-50">{busy ? 'Deleting…' : 'Delete session'}</button>
      </div>
    </Modal>
  )
}
