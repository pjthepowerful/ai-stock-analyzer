import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'
export type ThemePref = Theme

// index.html applies the theme before first paint (no flash); this module
// owns changing it afterwards. Until someone picks Light or Dark, Paula
// follows the device (there's no visible "System" option — it's just the
// default). A stored 'system' from early 5.0 builds counts as no choice.
const KEY = 'paula-theme'
const EVENT = 'paula-theme'
const DARK_MQ = '(prefers-color-scheme: dark)'

/** The explicit choice, or null when following the device. */
function readPref(): Theme | null {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

function systemTheme(): Theme {
  return window.matchMedia?.(DARK_MQ).matches ? 'dark' : 'light'
}

function apply(theme: Theme) {
  if (theme === 'dark') document.documentElement.dataset.theme = 'dark'
  else delete document.documentElement.dataset.theme
  window.dispatchEvent(new Event(EVENT))
}

// Follow the device live while no choice has been made.
window.matchMedia?.(DARK_MQ).addEventListener?.('change', () => {
  if (!readPref()) apply(systemTheme())
})

/** The theme actually on screen right now. */
export function getTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

export function setThemePref(pref: ThemePref) {
  try {
    localStorage.setItem(KEY, pref)
  } catch {
    /* private mode — the choice just won't persist */
  }
  apply(pref)
}

/** [theme on screen, the switch's selection (same thing — following the
 *  device just selects whichever it resolved to), setter]. Charts key their
 *  redraw on the theme. */
export function useTheme(): [Theme, ThemePref, (p: ThemePref) => void] {
  const [theme, setTheme] = useState(getTheme)
  useEffect(() => {
    const on = () => setTheme(getTheme())
    window.addEventListener(EVENT, on)
    return () => window.removeEventListener(EVENT, on)
  }, [])
  return [theme, theme, setThemePref]
}

export interface ChartColors {
  text: string
  grid: string
  border: string
  up: string
  down: string
  sma: string
  ema: string
}

/** Resolved chart colors for the current theme. lightweight-charts draws on a
 *  canvas, so it can't use CSS variables directly — read them here and
 *  redraw when the theme changes (components key their effect on `theme`). */
export function chartColors(): ChartColors {
  const css = getComputedStyle(document.documentElement)
  const v = (name: string) => css.getPropertyValue(name).trim()
  return {
    text: v('--chart-text'),
    grid: v('--chart-grid'),
    border: v('--border'),
    up: v('--chart-up'),
    down: v('--chart-down'),
    sma: v('--chart-sma'),
    ema: v('--chart-ema'),
  }
}

/** '#12976a' + 0.25 → 'rgba(18,151,106,0.25)' for area/volume fills. */
export function withAlpha(hex: string, alpha: number): string {
  const m = hex.replace('#', '').match(/^([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i)
  if (!m) return hex
  const [r, g, b] = m.slice(1).map((x) => parseInt(x, 16))
  return `rgba(${r},${g},${b},${alpha})`
}
