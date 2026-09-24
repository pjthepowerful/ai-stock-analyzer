import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import './toast.css'

interface Toast {
  id: number
  message: string
  action?: { label: string; run: () => void }
}

interface ToastApi {
  show: (message: string, action?: Toast['action']) => void
}

const ToastContext = createContext<ToastApi | null>(null)
const DURATION = 5000

/** Small notices in the corner, with an optional action (e.g. Undo). */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), [])

  const show = useCallback<ToastApi['show']>(
    (message, action) => {
      const id = nextId.current++
      setToasts((t) => [...t.slice(-2), { id, message, action }])
      setTimeout(() => dismiss(id), DURATION)
    },
    [dismiss],
  )

  const api = useMemo(() => ({ show }), [show])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className="toast">
            <span className="toast-msg">{t.message}</span>
            {t.action && (
              <button
                className="toast-action"
                onClick={() => {
                  t.action!.run()
                  dismiss(t.id)
                }}
              >
                {t.action.label}
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
