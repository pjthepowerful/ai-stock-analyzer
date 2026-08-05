import { useEffect, useMemo, useRef, useState } from 'react'
import './LandingPage.css'

const CHIPS = [
  {
    q: 'Why is NVDA flagged?',
    segs: [
      { t: "NVDA cleared yesterday's high at " },
      { t: '183.90', hl: true },
      { t: ' and held the reclaim. ' },
      { t: 'Confluence 5', hl: true },
      { t: ', stacked above the ' },
      { t: '9/21/50 EMA', hl: true },
      { t: ', volume ' },
      { t: '1.8×', hl: true },
      { t: " its 20-day average. That's a continuation setup, not a breakout guess." },
    ],
  },
  {
    q: "What's my risk on this?",
    segs: [
      { t: 'At ' },
      { t: '200 shares', hl: true },
      { t: ' from ' },
      { t: '181.40', hl: true },
      { t: ', your stop at ' },
      { t: '178.00', hl: true },
      { t: ' risks ' },
      { t: '$680', hl: true },
      { t: ' — 1.1% of the account. Target ' },
      { t: '189.20', hl: true },
      { t: ' pays ' },
      { t: '$1,560', hl: true },
      { t: ', so you’re taking ' },
      { t: '2.3:1', hl: true },
      { t: ". Under 2:1 I'd tell you to pass." },
    ],
  },
  {
    q: 'Should I trim?',
    segs: [
      { t: "You're up " },
      { t: '$500', hl: true },
      { t: ' and price is extended ' },
      { t: '1.4 ATR', hl: true },
      { t: ' from the ' },
      { t: '9-EMA', hl: true },
      { t: '. Trimming half locks ' },
      { t: '$250', hl: true },
      { t: ' and moves your stop to breakeven; the rest rides to ' },
      { t: '189.20', hl: true },
      { t: '. I have no read on whether it keeps going — I only know your risk is already paid for.' },
    ],
  },
]

const SCAN = [
  { sym: 'NVDA', base: 183.9, chg: 2.14, why: 'cleared PDH · held reclaim · vol 1.8×', conf: '5 / 5' },
  { sym: 'COIN', base: 288.44, chg: 3.07, why: 'range expansion · vol 2.3×', conf: '4 / 5' },
  { sym: 'MU', base: 114.1, chg: 1.62, why: 'flag over VWAP · RR 2.8:1', conf: '4 / 5' },
  { sym: 'AMD', base: 166.95, chg: -0.74, why: 'pullback to 20-EMA · RR 2.4:1', conf: '3 / 5' },
  { sym: 'SMCI', base: 41.79, chg: 0.46, why: 'inside day · coiling under 42.00', conf: '3 / 5' },
  { sym: 'TSLA', base: 331.2, chg: -1.28, why: 'lost 9-EMA · no long trigger', conf: '1 / 5' },
]

const POS = [
  { sym: 'NVDA', sh: 200, entry: 181.4, last: 183.9, stop: 178.0, target: 189.2 },
  { sym: 'AMD', sh: 150, entry: 168.2, last: 166.95, stop: 164.5, target: 174.6 },
  { sym: 'MU', sh: 100, entry: 112.85, last: 114.1, stop: 110.4, target: 119.75 },
  { sym: 'SMCI', sh: 300, entry: 41.6, last: 41.79, stop: 40.35, target: 44.1 },
]

const TYPING_SPEED_MS = 14

const money = (n) => (n < 0 ? '−$' : '+$') + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function pad(v) {
  return String(v).padStart(2, '0')
}

function useMountReveal() {
  const [in_, setIn] = useState(false)
  useEffect(() => {
    const raf = requestAnimationFrame(() => setIn(true))
    return () => cancelAnimationFrame(raf)
  }, [])
  return in_
}

function Reveal({ children, as: Tag = 'div', delay = 0, className = '', ...rest }) {
  const ref = useRef(null)
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return
        setInView(true)
        io.disconnect()
      },
      { threshold: 0.15, rootMargin: '0px 0px -40px 0px' }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return (
    <Tag ref={ref} className={`lp-reveal ${inView ? 'lp-reveal-in' : ''} ${className}`} style={{ transitionDelay: `${delay}ms` }} {...rest}>
      {children}
    </Tag>
  )
}

export default function LandingPage({ onLaunch }) {
  const [clock, setClock] = useState(() => {
    const d = new Date()
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  })
  const [drift, setDrift] = useState(() => SCAN.map(() => 0))
  const [heroPl, setHeroPl] = useState(395.8)
  const [chipIndex, setChipIndex] = useState(0)
  const [chars, setChars] = useState(0)
  const [statProgress, setStatProgress] = useState(0)
  const [tick, setTick] = useState(0)
  const statGridRef = useRef(null)
  const heroIn = useMountReveal()

  useEffect(() => {
    const t = setInterval(() => {
      const d = new Date()
      setClock(`${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`)
    }, 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const t = setInterval(() => {
      setDrift(SCAN.map((r) => (Math.random() - 0.5) * r.base * 0.0012))
      setHeroPl(395.8 + (Math.random() - 0.45) * 18)
      setTick((n) => n + 1)
    }, 1600)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    setChars(0)
    const full = CHIPS[chipIndex].segs.reduce((a, s) => a + s.t.length, 0)
    const t = setInterval(() => {
      setChars((c) => {
        if (c >= full) {
          clearInterval(t)
          return full
        }
        return Math.min(full, c + 2)
      })
    }, TYPING_SPEED_MS)
    return () => clearInterval(t)
  }, [chipIndex])

  const [statsRevealed, setStatsRevealed] = useState(false)

  useEffect(() => {
    const el = statGridRef.current
    if (!el) return
    let raf
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting) return
        observer.disconnect()
        setStatsRevealed(true)
        const t0 = Date.now()
        const dur = 1100
        const tick = () => {
          const p = Math.min(1, (Date.now() - t0) / dur)
          setStatProgress(1 - Math.pow(1 - p, 3))
          if (p < 1) raf = requestAnimationFrame(tick)
        }
        raf = requestAnimationFrame(tick)
      },
      { threshold: 0.1 }
    )
    observer.observe(el)
    return () => {
      observer.disconnect()
      if (raf) cancelAnimationFrame(raf)
    }
  }, [])

  const rows = useMemo(
    () =>
      SCAN.map((r, i) => ({
        sym: r.sym,
        price: (r.base + (drift[i] || 0)).toFixed(2),
        chg: (r.chg > 0 ? '+' : '−') + Math.abs(r.chg).toFixed(2) + '%',
        up: r.chg >= 0,
        why: r.why,
        conf: r.conf,
      })),
    [drift]
  )

  const positions = useMemo(
    () =>
      POS.map((p) => {
        const pl = (p.last - p.entry) * p.sh
        const win = (p.target - p.entry) * p.sh
        const lose = (p.stop - p.entry) * p.sh
        return {
          sym: p.sym,
          size: `${p.sh} sh · avg ${p.entry.toFixed(2)}`,
          pl: money(pl),
          up: pl >= 0,
          stop: p.stop.toFixed(2),
          target: p.target.toFixed(2),
          win: money(win),
          lose: money(lose),
          rr: Math.abs(win / lose).toFixed(1) + ':1',
        }
      }),
    []
  )

  const totalPl = useMemo(() => money(POS.reduce((a, p) => a + (p.last - p.entry) * p.sh, 0)), [])

  const replySegs = useMemo(() => {
    let n = chars
    const out = []
    for (const seg of CHIPS[chipIndex].segs) {
      if (n <= 0) break
      out.push({ t: seg.t.slice(0, n), hl: !!seg.hl })
      n -= seg.t.length
    }
    return out
  }, [chipIndex, chars])

  const fullLen = CHIPS[chipIndex].segs.reduce((a, s) => a + s.t.length, 0)
  const typing = chars < fullLen

  const stats = useMemo(
    () => [
      { value: `−${(2.1 * statProgress).toFixed(1)} pts`, label: 'Tighter average loss vs unstructured trading', note: 'stop + target defined before entry' },
      { value: `${Math.round(38 * statProgress)}% faster`, label: 'Time-to-exit on closed positions', note: 'no waiting to be right' },
      { value: `${Math.round(100 * statProgress)}%`, label: 'Of picks come with cited reasoning you can check', note: 'every signal, every time' },
    ],
    [statProgress]
  )

  return (
    <div className="landing-page">
      <nav className="lp-nav">
        <div className="lp-nav-brand">
          <span className="lp-logo">P</span>
          <b className="lp-wordmark">Paula</b>
        </div>
        <div className="lp-nav-spacer" />
        <button className="lp-btn-primary" onClick={onLaunch}>
          Sign in →
        </button>
      </nav>

      <div className="lp-hero">
        <div className="lp-hero-glow" />
        <div className="lp-hero-inner r-split r-hero">
          <div>
            <h1 className={`lp-hero-title lp-mount ${heroIn ? 'lp-mount-in' : ''}`} style={{ transitionDelay: '90ms' }}>
              Every trade, <span className="lp-hero-accent">reasoned through</span> before it's placed.
            </h1>
            <p className={`lp-hero-sub lp-mount ${heroIn ? 'lp-mount-in' : ''}`} style={{ transitionDelay: '180ms' }}>
              A live scanner, a chat copilot that shows its reasoning, and a position tracker that stays honest about where you stand.{' '}
              <b>Paula is not a stock-picking oracle.</b>
            </p>
            <div className={`lp-hero-ctas lp-mount ${heroIn ? 'lp-mount-in' : ''}`} style={{ transitionDelay: '270ms' }}>
              <button className="lp-btn-dark" onClick={onLaunch}>
                Launch app →
              </button>
              <a href="#copilot" className="lp-watch-link">
                <span className="lp-watch-icon">▶</span>
                Watch it think →
              </a>
            </div>
          </div>

          <div className={`lp-preview-card lp-mount lp-mount-scale ${heroIn ? 'lp-mount-in' : ''}`} style={{ transitionDelay: '220ms' }}>
            <div className="lp-preview-header">
              <span className="lp-preview-dot" />
              <span className="lp-preview-title">Paula — session preview</span>
              <span className="lp-preview-sub">/ sample data</span>
              <div className="lp-nav-spacer" />
              <span className="lp-preview-clock">{clock}</span>
            </div>
            <div className="lp-preview-body">
              <div className="lp-preview-block">
                <div className="lp-preview-label">Chat</div>
                <div className="lp-preview-chat">
                  <div className="lp-chat-q">Why is NVDA flagged?</div>
                  <div className="lp-chat-a">
                    Cleared yesterday's high at <span className="lp-mono-accent">183.90</span> and held the reclaim.{' '}
                    <span className="lp-mono-accent">Confluence 5</span>, volume <span className="lp-mono-accent">1.8×</span> its
                    20-day average.
                  </div>
                </div>
              </div>
              <div className="lp-preview-block">
                <div className="lp-preview-label">Live watchlist</div>
                <div className="lp-watchlist">
                  {rows.slice(0, 3).map((r) => (
                    <div className="lp-watchlist-row" key={r.sym}>
                      <span className="lp-watchlist-sym">{r.sym}</span>
                      <span className="lp-watchlist-price lp-flash" key={`p-${r.sym}-${tick}`}>
                        {r.price}
                      </span>
                      <span className={`lp-watchlist-chg lp-flash ${r.up ? 'up' : 'down'}`} key={`c-${r.sym}-${tick}`}>
                        {r.chg}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="lp-tracker-row">
                <div className="lp-preview-label">Tracker</div>
                <div className="lp-nav-spacer" />
                <div className="lp-tracker-value lp-flash" key={`tracker-${tick}`}>
                  {money(heroPl)}
                </div>
                <div className="lp-tracker-note">· open P/L · 4 positions</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="lp-wordband">
        <div className="lp-wordband-row">
          <span className="lp-word">confluence</span>
          <span className="lp-word-green">reclaim</span>
          <span className="lp-word-outline">vwap</span>
          <span className="lp-word">confluence</span>
          <span className="lp-word-green">reclaim</span>
          <span className="lp-word-outline">vwap</span>
        </div>
        <div className="lp-wordband-row lp-wordband-row-2">
          <span className="lp-word-outline">the tape</span>
          <span className="lp-word">momentum</span>
          <span className="lp-word-green">risk first</span>
          <span className="lp-word-outline">the tape</span>
          <span className="lp-word">momentum</span>
          <span className="lp-word-green">risk first</span>
        </div>
      </div>

      <section id="copilot" className="lp-section r-pad">
        <Reveal className="lp-eyebrow">01 / Copilot chat</Reveal>
        <Reveal as="h2" delay={70} className="lp-h2 lp-h2-narrow">
          It answers with the reason, not the verdict.
        </Reveal>
        <Reveal as="p" delay={140} className="lp-p">
          Every reply cites the signals behind it. You can disagree with the read — because you can see it.
        </Reveal>

        <div className="lp-copilot-panel">
          <div className="lp-copilot-header">
            <span className="lp-preview-title">Copilot</span>
            <span className="lp-preview-sub">/ sample data</span>
          </div>
          <div className="lp-copilot-body">
            {CHIPS.map((c) => (
              <Reveal key={c.q} className="lp-copilot-exchange">
                <div className="lp-copilot-user-row">
                  <div className="lp-copilot-user-bubble">{c.q}</div>
                </div>
                <div className="lp-copilot-reply-row">
                  <span className="lp-logo lp-logo-sm">P</span>
                  <div className="lp-copilot-reply-text">
                    {c.segs.map((s, j) => (
                      <span key={j} className={s.hl ? 'seg-hl' : undefined}>{s.t}</span>
                    ))}
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section id="scanner" className="lp-section r-pad lp-section-tight">
        <Reveal className="lp-eyebrow">02 / Live scanner</Reveal>
        <Reveal as="h2" delay={70} className="lp-h2">
          The market, filtered to what's actually setting up.
        </Reveal>
        <Reveal as="p" delay={140} className="lp-p">
          Six hundred symbols in, a handful out. Each row carries the reason it made the cut.
        </Reveal>

        <Reveal delay={100} className="lp-scanner-card">
          <div className="lp-scanner-scroll">
            <div className="lp-scanner-inner">
              <div className="lp-scanner-head">
                <div>Symbol</div>
                <div className="right">Last</div>
                <div className="right">Chg</div>
                <div>Why</div>
                <div className="right">Confluence</div>
              </div>
              {rows.map((r, i) => (
                <div className="lp-scanner-row lp-stagger-item" style={{ transitionDelay: `${i * 45}ms` }} key={r.sym}>
                  <div className="lp-scan-sym">{r.sym}</div>
                  <div className="lp-scan-price right lp-flash" key={`sp-${r.sym}-${tick}`}>
                    {r.price}
                  </div>
                  <div className={`lp-scan-chg right lp-flash ${r.up ? 'up' : 'down'}`} key={`sc-${r.sym}-${tick}`}>
                    {r.chg}
                  </div>
                  <div className="lp-scan-why">{r.why}</div>
                  <div className="lp-scan-conf right">{r.conf}</div>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
        <div className="lp-scan-note">Sample data · simulated ticks · last scan {clock} CT</div>
      </section>

      <section className="lp-section r-pad lp-section-tight">
        <Reveal className="lp-eyebrow">03 / Position tracker</Reveal>
        <Reveal as="h2" delay={70} className="lp-h2">
          You always know exactly where you stand.
        </Reveal>
        <Reveal as="p" delay={140} className="lp-p">
          Sized on purpose. Exited on time. No surprises.
        </Reveal>

        <Reveal delay={100} className="lp-summary-bar r-summary">
          <div>
            <div className="lp-summary-label">Open P/L</div>
            <div className="lp-summary-value up">{totalPl}</div>
          </div>
          <div>
            <div className="lp-summary-label">Risk at work</div>
            <div className="lp-summary-value">$1,595.50</div>
          </div>
          <div>
            <div className="lp-summary-label">Blended R:R</div>
            <div className="lp-summary-value">2.2:1</div>
          </div>
          <div className="lp-nav-spacer" />
          <div className="lp-summary-note">4 positions · sample data</div>
        </Reveal>

        <Reveal delay={160} className="lp-positions-grid">
          {positions.map((p, i) => (
            <div className="lp-pos-card lp-stagger-item" style={{ transitionDelay: `${i * 80}ms` }} key={p.sym}>
              <div className="lp-pos-head">
                <div className="lp-pos-sym">{p.sym}</div>
                <div className="lp-pos-size">{p.size}</div>
                <div className="lp-nav-spacer" />
                <div className={`lp-pos-pl ${p.up ? 'up' : 'down'}`}>{p.pl}</div>
              </div>
              <div className="lp-pos-metrics">
                <div className="lp-pos-metric">
                  <div className="lp-pos-metric-label">Stop</div>
                  <div className="lp-pos-metric-value">{p.stop}</div>
                </div>
                <div className="lp-pos-metric">
                  <div className="lp-pos-metric-label">Target</div>
                  <div className="lp-pos-metric-value">{p.target}</div>
                </div>
              </div>
              <div className="lp-pos-outcomes">
                <div className="lp-pos-outcome-row">
                  <span>If target hit</span>
                  <span className="up">{p.win}</span>
                </div>
                <div className="lp-pos-outcome-row">
                  <span>If stop hit</span>
                  <span className="down">{p.lose}</span>
                </div>
                <div className="lp-pos-rr-row">
                  <span>Reward:risk</span>
                  <span>{p.rr}</span>
                </div>
              </div>
            </div>
          ))}
        </Reveal>
      </section>

      <section className="lp-section r-pad lp-honesty">
        <Reveal className="lp-honesty-eyebrow">04 / The honesty advantage</Reveal>
        <Reveal as="h2" delay={70} className="lp-honesty-title">
          Tighter losses.
          <br />
          Faster exits.
          <br />
          <span className="lp-honesty-accent">Reasoning you can audit.</span>
        </Reveal>

        <div className={`lp-stat-grid ${statsRevealed ? 'lp-reveal-in' : ''}`} ref={statGridRef}>
          {stats.map((s, i) => (
            <div className="lp-stat-card lp-stagger-item" style={{ transitionDelay: `${i * 90}ms` }} key={s.label}>
              <div className="lp-stat-value">{s.value}</div>
              <div className="lp-stat-label">{s.label}</div>
              <div className="lp-stat-spacer" />
              <div className="lp-stat-note">{s.note}</div>
            </div>
          ))}
        </div>

        <Reveal delay={120} className="lp-quote-band r-field">
          <p className="lp-quote-text">
            We publish our out-of-sample results — including the ones most tools hide. We don't sell you alpha. We help you
            trade the market on purpose.
          </p>
          <span className="lp-quote-tag">Published quarterly</span>
        </Reveal>

        <Reveal delay={160} className="lp-footnote">
          <p>On raw stock-picking, our signal roughly tracks the S&amp;P — so we don't pretend to beat it. We make you a more disciplined trader instead.</p>
        </Reveal>
      </section>

      <section id="cta" className="lp-closer r-pad">
        <Reveal as="h2" className="lp-closer-title">
          Trade with a copilot
          <br />
          that shows its work.
        </Reveal>
        <Reveal delay={100} className="lp-closer-cta">
          <button className="lp-closer-btn" onClick={onLaunch}>
            Launch app →
          </button>
        </Reveal>
        <Reveal as="p" delay={160} className="lp-closer-note">
          Paula is a research and execution tool, not financial advice.
        </Reveal>
      </section>

      <div className="lp-footer">
        <span>Paula</span>
        <span className="lp-footer-rule" />
        <span>All figures on this page are sample data</span>
        <span className="lp-footer-rule" />
        <span>Not financial advice</span>
      </div>
    </div>
  )
}
