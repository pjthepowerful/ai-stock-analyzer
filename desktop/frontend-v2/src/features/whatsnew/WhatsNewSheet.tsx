import { ChevronDown, Play } from 'lucide-react'
import { useState } from 'react'
import { Sheet } from '../../components/Sheet'
import { HISTORY } from '../../lib/changelog-history'
import { RELEASES, VERSION, type Demo } from '../../lib/changelog'
import { BeforeAfter } from './BeforeAfter'
import './whatsnew.css'

interface Props {
  open: boolean
  onClose: () => void
}

/** Release notes: the current release's highlights (with Before / After
 *  demos for big changes), then every earlier release, collapsible. */
export function WhatsNewSheet({ open, onClose }: Props) {
  const [demo, setDemo] = useState<Demo | null>(null)
  const latest = RELEASES[0]
  const older = [
    ...RELEASES.slice(1).map((r) => ({ v: r.v, d: r.d, changes: r.changes })),
    ...HISTORY,
  ]

  function close() {
    setDemo(null)
    onClose()
  }

  return (
    <Sheet open={open} onClose={close} title={demo ? 'Before and after' : 'What’s new'} width={demo ? 960 : 640}>
      {demo ? (
        <div className="wn-demo">
          <BeforeAfter before={demo.before} after={demo.after} />
          <p className="wn-caption">{demo.caption}</p>
          <button className="btn btn-secondary" onClick={() => setDemo(null)}>
            Back to release notes
          </button>
        </div>
      ) : (
        <div className="wn">
          <div className="wn-release-head">
            <span className="badge badge-green">v{latest.v}</span>
            <span className="wn-date">{latest.d}</span>
          </div>
          {latest.title && <h3 className="wn-title">{latest.title}</h3>}

          {latest.highlights && (
            <ul className="wn-highlights">
              {latest.highlights.map((h) => (
                <li key={h.title} className="wn-hl">
                  <div className="wn-hl-text">
                    <strong>{h.title}</strong>
                    <p>{h.desc}</p>
                  </div>
                  {h.demo && (
                    <button className="btn btn-secondary btn-sm wn-demo-btn" onClick={() => setDemo(h.demo!)}>
                      <Play size={12} />
                      Demo
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}

          <ul className="wn-changes">
            {latest.changes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>

          <p className="wn-older-label">Earlier releases</p>
          <div className="wn-older">
            {older.slice(0, 40).map((r) => (
              <OlderRelease key={r.v} v={r.v} d={r.d} changes={r.changes} />
            ))}
          </div>
          <p className="wn-foot">You’re on Paula {VERSION}.</p>
        </div>
      )}
    </Sheet>
  )
}

function OlderRelease({ v, d, changes }: { v: string; d: string; changes: string[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={'wn-rel' + (open ? ' wn-rel-open' : '')}>
      <button className="wn-rel-head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="wn-rel-v">v{v}</span>
        <span className="wn-date">{d}</span>
        <ChevronDown size={14} className="wn-rel-chev" />
      </button>
      {open && (
        <ul className="wn-changes wn-changes-older">
          {changes.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
