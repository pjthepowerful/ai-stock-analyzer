// Sound effects using Web Audio API — no external files needed

let audioCtx = null

function getCtx() {
  if (!audioCtx) {
    try { audioCtx = new (window.AudioContext || window.webkitAudioContext)() } catch { return null }
  }
  if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {})
  return audioCtx
}

export function playBuy() {
  const ctx = getCtx(); if (!ctx) return
  const osc = ctx.createOscillator(), gain = ctx.createGain()
  osc.connect(gain); gain.connect(ctx.destination)
  osc.type = 'sine'
  osc.frequency.setValueAtTime(500, ctx.currentTime)
  osc.frequency.linearRampToValueAtTime(800, ctx.currentTime + 0.15)
  gain.gain.setValueAtTime(0.4, ctx.currentTime)
  gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.25)
  osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.25)
}

export function playSell() {
  const ctx = getCtx(); if (!ctx) return
  const osc = ctx.createOscillator(), gain = ctx.createGain()
  osc.connect(gain); gain.connect(ctx.destination)
  osc.type = 'sine'
  osc.frequency.setValueAtTime(700, ctx.currentTime)
  osc.frequency.linearRampToValueAtTime(350, ctx.currentTime + 0.2)
  gain.gain.setValueAtTime(0.4, ctx.currentTime)
  gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.3)
  osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.3)
}

export function playNotify() {
  const ctx = getCtx(); if (!ctx) return
  for (let i = 0; i < 2; i++) {
    const osc = ctx.createOscillator(), gain = ctx.createGain()
    osc.connect(gain); gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.setValueAtTime(600, ctx.currentTime + i * 0.18)
    gain.gain.setValueAtTime(0.3, ctx.currentTime + i * 0.18)
    gain.gain.linearRampToValueAtTime(0, ctx.currentTime + i * 0.18 + 0.12)
    osc.start(ctx.currentTime + i * 0.18); osc.stop(ctx.currentTime + i * 0.18 + 0.12)
  }
}

export function playAlert() {
  const ctx = getCtx(); if (!ctx) return
  const osc = ctx.createOscillator(), gain = ctx.createGain()
  osc.connect(gain); gain.connect(ctx.destination)
  osc.type = 'square'
  osc.frequency.setValueAtTime(300, ctx.currentTime)
  gain.gain.setValueAtTime(0.2, ctx.currentTime)
  gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.4)
  osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.4)
}

export function playProfit() {
  const ctx = getCtx(); if (!ctx) return
  const notes = [523, 659, 784]
  notes.forEach((freq, i) => {
    const osc = ctx.createOscillator(), gain = ctx.createGain()
    osc.connect(gain); gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.setValueAtTime(freq, ctx.currentTime + i * 0.12)
    gain.gain.setValueAtTime(0.3, ctx.currentTime + i * 0.12)
    gain.gain.linearRampToValueAtTime(0, ctx.currentTime + i * 0.12 + 0.25)
    osc.start(ctx.currentTime + i * 0.12); osc.stop(ctx.currentTime + i * 0.12 + 0.25)
  })
}

export function playTick() {
  const ctx = getCtx(); if (!ctx) return
  const osc = ctx.createOscillator(), gain = ctx.createGain()
  osc.connect(gain); gain.connect(ctx.destination)
  osc.type = 'sine'
  osc.frequency.setValueAtTime(1000, ctx.currentTime)
  gain.gain.setValueAtTime(0.15, ctx.currentTime)
  gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.05)
  osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.05)
}
