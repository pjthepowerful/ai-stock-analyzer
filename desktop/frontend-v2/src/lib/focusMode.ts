// Marks <html data-kbd> while the user is navigating by keyboard, so focus
// rings show for Tab / arrow-key users but never after a mouse click — not
// even when a modifier like Shift is pressed afterwards.
const NAV_KEYS = new Set(['Tab', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown'])

export function installFocusMode() {
  const root = document.documentElement
  window.addEventListener(
    'keydown',
    (e) => {
      if (NAV_KEYS.has(e.key)) root.setAttribute('data-kbd', '')
    },
    true,
  )
  window.addEventListener('pointerdown', () => root.removeAttribute('data-kbd'), true)
}
