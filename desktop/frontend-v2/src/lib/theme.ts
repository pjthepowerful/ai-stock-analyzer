import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

// index.html applies the stored theme before first paint (no flash); this
// module owns changing it afterwards.
const KEY = 'paula-v2-theme'
const EVENT = 'paula-theme'

export function getTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

export function setTheme(theme: Theme) {
  if (theme === 'dark') document.documentElement.dataset.theme = 'dark'
  else delete document.documentElement.dataset.theme
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    /* private mode — the choice just won't persist */
  }
  window.dispatchEvent(new Event(EVENT))
}

export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setState] = useState<Theme>(getTheme)
  useEffect(() => {
    const on = () => setState(getTheme())
    window.addEventListener(EVENT, on)
    return () => window.removeEventListener(EVENT, on)
  }, [])
  return [theme, setTheme]
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
