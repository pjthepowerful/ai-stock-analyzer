import { useState } from 'react'
import { Sheet } from '../../components/Sheet'
import { api, ApiError, type ChatMessage } from '../../lib/api'
import './feedback.css'

interface Props {
  open: boolean
  onClose: () => void
  transcript?: ChatMessage[]
}

export function ReportSheet({ open, onClose, transcript }: Props) {
  return (
    <Sheet open={open} onClose={onClose} title="Report a problem">
      {/* Mounted only while open, so every opening starts with a fresh form. */}
      {open && <ReportForm onClose={onClose} transcript={transcript} />}
    </Sheet>
  )
}

function ReportForm({ onClose, transcript }: Omit<Props, 'open'>) {
  const [note, setNote] = useState('')
  const [attach, setAttach] = useState(true)
  const [busy, setBusy] = useState(false)
  const [sentId, setSentId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const hasChat = !!transcript && transcript.length > 0

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const res = await api.post<{ ok: boolean; id: string }>('/api/report-bug', {
        note,
        messages: hasChat && attach ? transcript : [],
        version: 'v2-preview',
        user_agent: navigator.userAgent,
        url: location.href,
      })
      setSentId(res.id)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not send the report.')
    } finally {
      setBusy(false)
    }
  }

  return sentId ? (
    <div>
      <p className="fb-sent">
        Sent. Reference <span className="mono">{sentId}</span>.
      </p>
      <button className="btn btn-primary fb-submit" onClick={onClose}>
        Done
      </button>
    </div>
  ) : (
    <>
      <textarea
        className="input fb-note"
        placeholder="What happened, and what did you expect instead?"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={5}
      />
      {hasChat && (
        <label className="fb-attach">
          <input type="checkbox" checked={attach} onChange={(e) => setAttach(e.target.checked)} />
          Include this chat ({transcript!.length} messages)
        </label>
      )}
      <button className="btn btn-primary fb-submit" onClick={submit} disabled={busy || (!note.trim() && !(hasChat && attach))}>
        {busy ? 'Sending…' : 'Send report'}
      </button>
      {error && <p className="fb-error">{error}</p>}
    </>
  )
}
