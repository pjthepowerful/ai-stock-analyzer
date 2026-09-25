import { Check, ChevronDown, Sparkles, Zap } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'

export type ModelTier = 'smart' | 'fast'

interface Tier {
  id: ModelTier
  label: string
  model: string
}

const KEY = 'paula.modelTier'
// Paula's own names for the two modes; the underlying model shows beside them.
export const TIER_NAME: Record<ModelTier, string> = { smart: 'Prism', fast: 'Pulse' }
const BLURB: Record<ModelTier, string> = {
  smart: 'Sees every angle — best for analysis and trades',
  fast: 'A quick read — fastest replies for simple questions',
}

export function loadTier(): ModelTier {
  try {
    return localStorage.getItem(KEY) === 'fast' ? 'fast' : 'smart'
  } catch {
    return 'smart'
  }
}

let cached: Tier[] | null = null

/** Composer chip that picks the model tier, like the model menus in ChatGPT
    and t3.chat. The server maps a tier to a model on each provider. */
export function ModelPicker({ value, onChange }: { value: ModelTier; onChange: (t: ModelTier) => void }) {
  const [tiers, setTiers] = useState<Tier[] | null>(cached)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (cached) return
    api
      .get<{ tiers: Tier[] }>('/api/chat/models')
      .then((r) => {
        cached = r.tiers
        setTiers(r.tiers)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  const Icon = value === 'fast' ? Zap : Sparkles

  function pick(t: ModelTier) {
    onChange(t)
    setOpen(false)
    try {
      localStorage.setItem(KEY, t)
    } catch {
      /* per-browser convenience only */
    }
  }

  return (
    <div className="model-pick" ref={ref}>
      <button
        type="button"
        className="model-chip"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <Icon size={13} strokeWidth={2} />
        <span>Paula {TIER_NAME[value]}</span>
        <ChevronDown size={13} strokeWidth={2} className="model-chip-caret" />
      </button>
      {open && (
        <div className="model-menu" role="menu">
          {(tiers ?? []).map((t) => {
            const TIcon = t.id === 'fast' ? Zap : Sparkles
            return (
              <button
                key={t.id}
                type="button"
                role="menuitemradio"
                aria-checked={t.id === value}
                className="model-item"
                onClick={() => pick(t.id)}
              >
                <TIcon size={15} strokeWidth={1.8} className="model-item-icon" />
                <span className="model-item-text">
                  <span className="model-item-title">
                    Paula {TIER_NAME[t.id]}
                    <span className="model-item-name">{t.label}</span>
                  </span>
                  <span className="model-item-desc">{BLURB[t.id]}</span>
                </span>
                {t.id === value && <Check size={14} strokeWidth={2.2} className="model-item-check" />}
              </button>
            )
          })}
          {!tiers && <p className="model-menu-empty">Models unavailable</p>}
        </div>
      )}
    </div>
  )
}
