import { X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'
import './Sheet.css'

interface Props {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  width?: number
}

// Native <dialog> + showModal(): Esc-to-close, focus trapping and the inert
// backdrop come from the browser instead of being hand-rolled.
export function Sheet({ open, onClose, title, children, width = 520 }: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (open && !el.open) {
      el.showModal()
      // showModal() focuses the first focusable element — the esc button —
      // so typing a space straight away would close the sheet. Land on the
      // first field instead, or the panel itself when there isn't one.
      const field = el.querySelector<HTMLElement>('textarea, input, select')
      ;(field ?? el).focus()
    }
    if (!open && el.open) el.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      className="sheet"
      style={{ width }}
      tabIndex={-1}
      onClose={onClose}
      onClick={(e) => {
        // A click on the dialog element itself (not its content) is the backdrop.
        if (e.target === ref.current) onClose()
      }}
    >
      <div className="sheet-inner">
        <header className="sheet-head">
          <h2 className="sheet-title">{title}</h2>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </header>
        {children}
      </div>
    </dialog>
  )
}
