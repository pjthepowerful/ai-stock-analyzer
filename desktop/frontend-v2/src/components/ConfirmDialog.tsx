import type { ReactNode } from 'react'
import { Sheet } from './Sheet'
import './ConfirmDialog.css'

interface Props {
  open: boolean
  title: string
  /** What will happen, in plain words. */
  body: ReactNode
  confirmLabel: string
  /** Red confirm button for anything that takes something away. */
  danger?: boolean
  busy?: boolean
  error?: string | null
  onConfirm: () => void
  onCancel: () => void
  /** Extra fields (e.g. a message box) between the text and the buttons. */
  children?: ReactNode
}

/** "Are you sure?" for changes that matter — one sentence of consequence,
 *  Cancel on the left, the action on the right (the macOS/GitHub pattern). */
export function ConfirmDialog({ open, title, body, confirmLabel, danger, busy, error, onConfirm, onCancel, children }: Props) {
  return (
    <Sheet open={open} onClose={busy ? () => {} : onCancel} title={title} width={440}>
      <div className="confirm">
        <div className="confirm-body">{body}</div>
        {children}
        {error && <p className="confirm-error">{error}</p>}
        <div className="confirm-actions">
          <button className="btn btn-secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button className={'btn ' + (danger ? 'btn-danger' : 'btn-primary')} onClick={onConfirm} disabled={busy}>
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </Sheet>
  )
}
