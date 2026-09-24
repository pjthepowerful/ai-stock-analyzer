import { useEffect, useState } from 'react'
import './Typewriter.css'

const TYPE_MS = 55
const DELETE_MS = 28
const HOLD_MS = 5200
const GAP_MS = 350

/** Types a phrase, holds it, deletes it, moves to the next — the greeting
 *  line from the original app. People who ask for reduced motion get the
 *  first phrase, static. */
export function Typewriter({ phrases }: { phrases: string[] }) {
  const reduced =
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const [text, setText] = useState(reduced ? phrases[0] : '')

  useEffect(() => {
    if (reduced || phrases.length === 0) return
    let idx = 0
    let chars = 0
    let deleting = false
    let timer: ReturnType<typeof setTimeout>

    const step = () => {
      const phrase = phrases[idx % phrases.length]
      if (!deleting) {
        chars += 1
        setText(phrase.slice(0, chars))
        if (chars >= phrase.length) {
          deleting = true
          timer = setTimeout(step, HOLD_MS)
          return
        }
        timer = setTimeout(step, TYPE_MS)
      } else {
        chars -= 1
        setText(phrase.slice(0, chars))
        if (chars <= 0) {
          deleting = false
          idx += 1
          timer = setTimeout(step, GAP_MS)
          return
        }
        timer = setTimeout(step, DELETE_MS)
      }
    }
    timer = setTimeout(step, 400)
    return () => clearTimeout(timer)
  }, [phrases, reduced])

  return (
    <span className="tw" aria-label={phrases[0]}>
      <span aria-hidden>{text}</span>
      <span className="tw-caret" aria-hidden />
    </span>
  )
}
