import { Monitor, Moon, Sun, type LucideIcon } from 'lucide-react'
import { useTheme, type ThemePref } from '../lib/theme'

const OPTIONS: { id: ThemePref; label: string; icon: LucideIcon }[] = [
  { id: 'system', label: 'System', icon: Monitor },
  { id: 'light', label: 'Light', icon: Sun },
  { id: 'dark', label: 'Dark', icon: Moon },
]

/** Light / dark / follow-the-OS. Compact icon form for the sidebar (the
 *  Vercel/Geist pattern), labelled form for Settings. */
export function ThemeSwitch({ labels = false }: { labels?: boolean }) {
  const [, pref, setPref] = useTheme()
  return (
    <div className={'seg' + (labels ? '' : ' seg-icons')} role="radiogroup" aria-label="Theme">
      {OPTIONS.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          role="radio"
          aria-checked={pref === id}
          aria-label={label}
          title={label}
          className={'seg-btn' + (pref === id ? ' seg-on' : '')}
          onClick={() => setPref(id)}
        >
          <Icon size={14} strokeWidth={1.9} />
          {labels && label}
        </button>
      ))}
    </div>
  )
}
