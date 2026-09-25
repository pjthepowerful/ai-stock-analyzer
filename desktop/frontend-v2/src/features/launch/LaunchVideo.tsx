import { createPortal } from 'react-dom'
import './comingsoon.css'


/** The Paula 5 promo, full-screen. Plays at launch, and on demand from the
 *  owner's Team panel / Admin page as a preview. Portaled to <body> so no
 *  scrolled or transformed page can pull it off-center. */
export function LaunchVideo({ onDone }: { onDone: () => void }) {
  return createPortal(
    <div className="lv">
      <video src="/launch/paula5.mp4" autoPlay muted playsInline onEnded={onDone} onError={onDone} />
      <button className="lv-skip" onClick={onDone}>
        Skip →
      </button>
    </div>,
    document.body,
  )
}
