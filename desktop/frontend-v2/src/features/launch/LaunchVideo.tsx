import './comingsoon.css'


/** The Paula 5 promo, full-screen. Plays at launch, and on demand from the
 *  owner's Team panel / Admin page as a preview. */
export function LaunchVideo({ onDone }: { onDone: () => void }) {
  return (
    <div className="lv">
      <video src="/launch/paula5.mp4" autoPlay muted playsInline onEnded={onDone} onError={onDone} />
      <button className="lv-skip" onClick={onDone}>
        Skip →
      </button>
    </div>
  )
}
