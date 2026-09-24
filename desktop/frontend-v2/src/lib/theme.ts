import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'
export type ThemePref = Theme

// index.html applies the stored preference before first paint (no flash);
// this module owns changing it afterwards.
// New key for v5: everyone starts on the new black default once. A stored
// 'system' (offered in early 5.0 builds) now reads as dark.
const KEY = 'paula-theme'
const EVENT = 'paula-theme'

function readPref(): ThemePref {
  try {
    return localStorage.getItem(KEY) === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

function apply(theme: Theme) {
  if (theme === 'dark') document.documentElement.dataset.theme = 'dark'
  else delete document.documentElement.dataset.theme
  window.dispatchEvent(new Event(EVENT))
}

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

/** [resolved theme on screen, the person's preference, setter]. Charts key
 *  their redraw on the resolved theme. */
export function useTheme(): [Theme, ThemePref, (p: ThemePref) => void] {
  const [state, setState] = useState(() => ({ theme: getTheme(), pref: readPref() }))
  useEffect(() => {
    const on = () => setState({ theme: getTheme(), pref: readPref() })
    window.addEventListener(EVENT, on)
    return () => window.removeEventListener(EVENT, on)
  }, [])
  return [state.theme, state.pref, setThemePref]
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
