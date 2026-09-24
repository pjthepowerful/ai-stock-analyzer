import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import './ThankYou.css'

interface Row {
  icon: LucideIcon
  title: string
  desc: string
}

interface Props {
  title: string
  subtitle: ReactNode
  rows?: Row[]
  action: ReactNode
}

/** Confirmation moment after a purchase or a report: a check that draws
 *  itself, a short thank-you, what just changed, one next step. */
export function ThankYou({ title, subtitle, rows, action }: Props) {
  return (
    <div className="ty">
      <div className="ty-mark" aria-hidden>
        {Array.from({ length: 8 }, (_, i) => (
          <span key={i} className="ty-dot" style={{ ['--i' as string]: i }} />
        ))}
        <svg viewBox="0 0 52 52" className="ty-check">
          <circle cx="26" cy="26" r="24" className="ty-check-ring" />
          <path d="M15 27 l7 7 l15 -15" className="ty-check-tick" />
        </svg>
      </div>
      <h3 className="ty-title">{title}</h3>
      <p className="ty-sub">{subtitle}</p>
      {rows && rows.length > 0 && (
        <ul className="ty-rows">
          {rows.map(({ icon: Icon, title: t, desc }) => (
            <li key={t}>
              <span className="ty-row-icon">
                <Icon size={15} strokeWidth={1.9} />
              </span>
              <span>
                <strong>{t}</strong>
                <small>{desc}</small>
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="ty-action">{action}</div>
    </div>
  )
}
