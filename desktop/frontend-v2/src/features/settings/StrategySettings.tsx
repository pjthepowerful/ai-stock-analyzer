import { useQuery, useQueryClient } from '@tanstack/react-query'
import { RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { api, ApiError } from '../../lib/api'
import { useToast } from '../../lib/toast'

type Value = number | boolean | string | string[]

interface Knob {
  key: string
  group: string
  label: string
  type: 'pct' | 'pts' | 'num' | 'int' | 'bool' | 'time' | 'setups'
  min?: number | string
  max?: number | string
  step?: number
  unit?: string
  zero?: string
  help?: string
  options?: Record<string, string>
  default: Value
  value: Value
  custom: boolean
}

interface CustomResponse {
  ok: boolean
  mode: string
  knobs: Knob[]
}

/** Percent knobs are stored as fractions; the input works in percent. */
const toInput = (k: Knob, v: number) => (k.type === 'pct' ? +(v * 100).toFixed(3) : v)
const fromInput = (k: Knob, n: number) => (k.type === 'pct' ? +(n / 100).toFixed(6) : k.type === 'int' ? Math.round(n) : n)

function show(k: Knob, v: Value): string {
  if (typeof v === 'boolean') return v ? 'On' : 'Off'
  if (Array.isArray(v)) return v.map((s) => k.options?.[s] ?? s).join(', ')
  if (typeof v === 'string') return v
  if (v === 0 && k.zero) return k.zero
  if (k.type === 'pct') return `${+(v * 100).toFixed(2)}%`
  if (k.type === 'pts') return `${v}%`
  if (k.unit === '$') return `$${v}`
  return k.unit ? `${v} ${k.unit}` : String(v)
}

const same = (a: Value, b: Value) => JSON.stringify(a) === JSON.stringify(b)

interface Props {
  /** Strategy keys the owner can pick between, with display names. */
  modes: { key: string; label: string }[]
  /** The strategy autopilot is set to — opened first. */
  current?: string
  running: boolean
}

/** Owner-editable strategy settings. Edits stay local until Save; values
 *  apply from autopilot's next cycle. */
export function StrategySettings({ modes, current, running }: Props) {
  const qc = useQueryClient()
  const toast = useToast()
  const [mode, setMode] = useState(current && modes.some((m) => m.key === current) ? current : modes[0]?.key)
  const [draft, setDraft] = useState<Record<string, Value | null>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const q = useQuery({
    queryKey: ['autopilot-custom', mode],
    queryFn: () => api.get<CustomResponse>(`/api/autopilot/custom?mode=${mode}`),
    enabled: !!mode,
  })

  const knobs = q.data?.knobs ?? []
  const dirty = Object.keys(draft).length > 0
  const customCount = knobs.filter((k) => (k.key in draft ? draft[k.key] !== null : k.custom)).length

  function switchMode(key: string) {
    setDraft({})
    setError(null)
    setMode(key)
  }

  function edit(k: Knob, v: Value) {
    setError(null)
    setDraft((d) => {
      const next = { ...d }
      if (same(v, k.default)) {
        // Choosing the default is a reset: tell the server only if it has a custom value.
        if (k.custom) next[k.key] = null
        else delete next[k.key]
      } else if (k.custom && same(v, k.value)) {
        delete next[k.key] // back to what's saved
      } else {
        next[k.key] = v
      }
      return next
    })
  }

  function reset(k: Knob) {
    setError(null)
    setDraft((d) => {
      const next = { ...d }
      if (k.custom) next[k.key] = null
      else delete next[k.key]
      return next
    })
  }

  function resetAll() {
    const next: Record<string, null> = {}
    for (const k of knobs) if (k.custom) next[k.key] = null
    setDraft(next)
    setError(null)
  }

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const res = await api.put<CustomResponse>('/api/autopilot/custom', { mode, values: draft })
      qc.setQueryData(['autopilot-custom', mode], res)
      void qc.invalidateQueries({ queryKey: ['autopilot-modes'] })
      setDraft({})
      toast.show(running ? 'Saved — applies from the next scan' : 'Strategy settings saved')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not save.')
    } finally {
      setSaving(false)
    }
  }

  const groups = [...new Set(knobs.map((k) => k.group))]

  return (
    <div className="strat">
      <div className="strat-head">
        <div>
          <h3 className="strat-title">Customize strategy</h3>
          <p className="settings-section-note">
            Your values replace the strategy’s defaults, including its automatic adjustments. Changes apply
            from the next scan.
          </p>
        </div>
        {modes.length > 1 && (
          <div className="seg" role="tablist">
            {modes.map((m) => (
              <button
                key={m.key}
                className={'seg-btn' + (m.key === mode ? ' seg-on' : '')}
                onClick={() => switchMode(m.key)}
                // Save or discard first, so edits never silently vanish.
                disabled={dirty && m.key !== mode}
                title={dirty && m.key !== mode ? 'Save or discard your changes first' : undefined}
                role="tab"
                aria-selected={m.key === mode}
              >
                {m.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {q.isLoading && <div className="skeleton strat-skeleton" />}
      {q.error && <p className="note-warn">{q.error.message}</p>}

      {groups.map((g) => (
        <div key={g} className="strat-group">
          <p className="strat-group-title">{g}</p>
          {knobs
            .filter((k) => k.group === g)
            .map((k) => {
              const v = (k.key in draft ? (draft[k.key] ?? k.default) : k.value) as Value
              const isCustom = k.key in draft ? draft[k.key] !== null : k.custom
              const changed = k.key in draft
              return (
                <div key={k.key} className={'strat-row' + (changed ? ' strat-row-changed' : '')}>
                  <div className="strat-label">
                    <span>
                      {k.label}
                      {isCustom && <span className="strat-mark" title="Customized" />}
                    </span>
                    {k.help && <small>{k.help}</small>}
                    {isCustom && <small className="strat-default">Default: {show(k, k.default)}</small>}
                  </div>
                  <div className="strat-control">
                    <Control knob={k} value={v} onChange={(nv) => edit(k, nv)} />
                    <button
                      className="btn btn-ghost btn-icon btn-sm strat-reset"
                      onClick={() => reset(k)}
                      aria-label={`Reset ${k.label} to default`}
                      title="Reset to default"
                      style={{ visibility: isCustom ? 'visible' : 'hidden' }}
                    >
                      <RotateCcw size={13} />
                    </button>
                  </div>
                </div>
              )
            })}
        </div>
      ))}

      {knobs.length > 0 && (
        <div className="strat-foot">
          {error && <p className="strat-error">{error}</p>}
          <button className="btn btn-ghost btn-sm" onClick={resetAll} disabled={saving || customCount === 0}>
            Reset all to defaults
          </button>
          <span className="strat-spacer" />
          {dirty && (
            <button className="btn btn-secondary btn-sm" onClick={() => setDraft({})} disabled={saving}>
              Discard
            </button>
          )}
          <button className="btn btn-primary btn-sm" onClick={save} disabled={!dirty || saving}>
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      )}
    </div>
  )
}

function Control({ knob: k, value, onChange }: { knob: Knob; value: Value; onChange: (v: Value) => void }) {
  if (k.type === 'bool') {
    return (
      <button
        className={'strat-switch' + (value ? ' strat-switch-on' : '')}
        role="switch"
        aria-checked={!!value}
        aria-label={k.label}
        onClick={() => onChange(!value)}
      >
        <span />
      </button>
    )
  }
  if (k.type === 'time') {
    return (
      <input
        className="input strat-input"
        type="time"
        value={String(value)}
        min={String(k.min)}
        max={String(k.max)}
        step={300}
        aria-label={k.label}
        onChange={(e) => e.target.value && onChange(e.target.value)}
      />
    )
  }
  if (k.type === 'setups') {
    const on = new Set(value as string[])
    return (
      <div className="strat-chips">
        {Object.entries(k.options ?? {}).map(([key, label]) => (
          <button
            key={key}
            className={'strat-chip' + (on.has(key) ? ' strat-chip-on' : '')}
            aria-pressed={on.has(key)}
            onClick={() => {
              const next = new Set(on)
              if (next.has(key)) next.delete(key)
              else next.add(key)
              // Keep the server's canonical order.
              onChange(Object.keys(k.options ?? {}).filter((s) => next.has(s)))
            }}
          >
            {label}
          </button>
        ))}
      </div>
    )
  }
  return <NumberControl knob={k} value={value as number} onChange={onChange} />
}

function NumberControl({ knob: k, value, onChange }: { knob: Knob; value: number; onChange: (v: Value) => void }) {
  const scale = k.type === 'pct' ? 100 : 1
  const min = Number(k.min) * scale
  const max = Number(k.max) * scale
  const step = (k.step ?? 1) * scale
  // Text while typing, so "0." or an empty box doesn't snap back mid-edit.
  const [text, setText] = useState<string | null>(null)
  const shown = text ?? String(toInput(k, value))
  const suffix = k.type === 'pct' || k.type === 'pts' ? '%' : k.unit && k.unit !== '$' ? k.unit : ''

  function commit(raw: string) {
    setText(null)
    const n = Number(raw)
    if (raw.trim() === '' || !Number.isFinite(n)) return
    const clamped = Math.min(max, Math.max(min, n))
    onChange(fromInput(k, +clamped.toFixed(4)))
  }

  return (
    <div className="strat-num">
      {k.unit === '$' && <span className="strat-affix">$</span>}
      <input
        className="input strat-input mono"
        type="number"
        inputMode="decimal"
        value={shown}
        min={min}
        max={max}
        step={step}
        aria-label={k.label}
        onChange={(e) => {
          setText(e.target.value)
          const n = Number(e.target.value)
          // Arrow keys / spinner: apply straight away when it's a valid number.
          if (e.target.value !== '' && Number.isFinite(n) && n >= min && n <= max) onChange(fromInput(k, n))
        }}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && commit((e.target as HTMLInputElement).value)}
      />
      {/* Always rendered, so every box lines up whether or not it has a unit. */}
      <span className="strat-affix strat-suffix">{suffix}</span>
      {k.zero && value === 0 && <span className="strat-zero">{k.zero}</span>}
    </div>
  )
}
