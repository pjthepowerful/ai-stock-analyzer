// Sound effects using Web Audio API — no external files needed

let audioCtx = null
let unlocked = false

function getCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)()
  if (!unlocked && audioCtx.state === 'suspended') {
    audioCtx.resume()
  }
  unlocked = true
  return audioCtx
}

// Unlock audio on first user interaction
document.addEventListener('click', () => {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)()
  if (audioCtx.state === 'suspended') audioCtx.resume()
  unlocked = true
}, { once: false })

document.addEventListener('keydown', () => {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)()
  if (audioCtx.state === 'suspended') audioCtx.resume()
  unlocked = true
}, { once: false })

// Short rising tone — buy/long executed
export function playBuy() {
  const ctx = getCtx()
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)
  osc.type = 'sine'
  osc.frequency.setValueAtTime(500, ctx.currentTime)
  osc.frequency.linearRampToValueAtTime(800, ctx.currentTime + 0.15)
  gain.gain.setValueAtTime(0.4, ctx.currentTime)
  gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.25)
  osc.start(ctx.currentTime)
  osc.stop(ctx.currentTime + 0.25)
}

// Short falling tone — sell/short executed
export function playSell() {
  const ctx = getCtx()
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)
  osc.type = 'sine'
  osc.frequency.setValueAtTime(700, ctx.currentTime)
  osc.frequency.linearRampToValueAtTime(350, ctx.currentTime + 0.2)
  gain.gain.setValueAtTime(0.4, ctx.currentTime)
  gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.3)
  osc.start(ctx.currentTime)
  osc.stop(ctx.currentTime + 0.3)
}

// Double beep — autopilot scan complete
export function playNotify() {
  const ctx = getCtx()
  for (let i = 0; i < 2; i++) {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.setValueAtTime(600, ctx.currentTime + i * 0.18)
    gain.gain.setValueAtTime(0.3, ctx.currentTime + i * 0.18)
    gain.gain.linearRampToValueAtTime(0, ctx.currentTime + i * 0.18 + 0.12)
    osc.start(ctx.currentTime + i * 0.18)
    osc.stop(ctx.currentTime + i * 0.18 + 0.12)
  }
}

// Alert — error or warning
export function playAlert() {
  const ctx = getCtx()
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)
  osc.type = 'square'
  osc.frequency.setValueAtTime(300, ctx.currentTime)
  gain.gain.setValueAtTime(0.2, ctx.currentTime)
  gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.4)
  osc.start(ctx.currentTime)
  osc.stop(ctx.currentTime + 0.4)
}

// Success chime — position closed profitably
export function playProfit() {
  const ctx = getCtx()
  const notes = [523, 659, 784] // C E G
  notes.forEach((freq, i) => {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.setValueAtTime(freq, ctx.currentTime + i * 0.12)
    gain.gain.setValueAtTime(0.3, ctx.currentTime + i * 0.12)
    gain.gain.linearRampToValueAtTime(0, ctx.currentTime + i * 0.12 + 0.25)
    osc.start(ctx.currentTime + i * 0.12)
    osc.stop(ctx.currentTime + i * 0.12 + 0.25)
  })
}

// Message received — subtle tick
export function playTick() {
  const ctx = getCtx()
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)
  osc.type = 'sine'
  osc.frequency.setValueAtTime(1000, ctx.currentTime)
  gain.gain.setValueAtTime(0.15, ctx.currentTime)
  gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.05)
  osc.start(ctx.currentTime)
  osc.stop(ctx.currentTime + 0.05)
}
