// Chat message formatting. Order matters: HTML-escape first, then add back a
// small set of known-safe tags, so model or scan output can never inject
// markup of its own.

const PRICE = /\$\s?([\d,]+\.?\d*)/g

/**
 * Drop lines where the model has invented trade levels. It sometimes repeats
 * the current price as entry, stop AND target, or leaves one at zero; real
 * levels come only from the structured signal card. Ported from the original
 * app's "permanent guard".
 */
export function dropHallucinatedLevels(text: string): string {
  return text
    .split('\n')
    .filter((line) => {
      const m = line.match(/entry[:\s]*\$?([\d.,]+).*stop[:\s]*\$?([\d.,]+).*target[:\s]*\$?([\d.,]+)/i)
      if (m) {
        const nums = [m[1], m[2], m[3]].map((n) => parseFloat(n.replace(/,/g, '')))
        if (nums.some((n) => !Number.isFinite(n) || n === 0)) return false
        const [a, b, c] = nums
        return !(Math.abs(a - b) < 0.01 && Math.abs(b - c) < 0.01)
      }
      if (/\bentry\b/i.test(line) && /(stop|target)/i.test(line)) {
        const prices = (line.match(PRICE) ?? []).map((p) => parseFloat(p.replace(/[$,\s]/g, '')))
        if (prices.length >= 2 && new Set(prices.map((p) => Math.round(p * 100))).size === 1) return false
      }
      return true
    })
    .join('\n')
}

function escapeHtml(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function host(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function formatMessage(raw: string): string {
  const text = dropHallucinatedLevels(raw)
  if (!text.trim()) return ''
  let s = escapeHtml(text)

  // [label](https://…) → link; bare https://… → link labelled by domain.
  // URLs are already entity-escaped above, so they're safe inside href="".
  s = s.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_, label: string, url: string) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`,
  )
  s = s.replace(
    /(^|[\s(])(https?:\/\/[^\s)<]+)/g,
    (_, pre: string, url: string) =>
      `${pre}<a href="${url}" target="_blank" rel="noopener noreferrer">${host(url.replace(/&amp;/g, '&'))}</a>`,
  )

  s = s
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Dollar amounts in tabular mono — but not inside the href/label we just made.
    .split(/(<[^>]+>)/g)
    .map((seg) => (seg.startsWith('<') ? seg : seg.replace(/\$(\d[\d,]*\.?\d*)/g, '<span class="mono num-hl">$$$1</span>')))
    .join('')
    .replace(/\n/g, '<br/>')
  return s
}
