// Paula Commercial — Animation Timeline Engine
const { createContext, useContext, useState, useEffect, useRef, useCallback } = React;

// Easing functions
const Easing = {
  linear: t => t,
  easeInCubic: t => t * t * t,
  easeOutCubic: t => 1 - Math.pow(1 - t, 3),
  easeInOutCubic: t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
  easeOutBack: t => { const c1 = 1.70158; const c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
  easeInBack: t => { const c1 = 1.70158; const c3 = c1 + 1; return c3 * t * t * t - c1 * t * t; },
  easeOutElastic: t => { if (t === 0 || t === 1) return t; return Math.pow(2, -10 * t) * Math.sin((t - 0.075) * (2 * Math.PI) / 0.3) + 1; },
};

// Animation helper — returns a function of time
function animate({ from = 0, to = 1, start = 0, end = 1, ease = Easing.linear }) {
  return (time) => {
    if (time <= start) return from;
    if (time >= end) return to;
    const t = (time - start) / (end - start);
    const eased = ease(Math.max(0, Math.min(1, t)));
    return from + (to - from) * eased;
  };
}

// Timeline context
const TimelineContext = createContext({ time: 0, duration: 20, playing: true });
function useTimeline() { return useContext(TimelineContext); }

// Stage component — manages playback
function Stage({ children, width = 1920, height = 1080, duration = 20, background = "#000" }) {
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const startRef = useRef(null);
  const rafRef = useRef(null);

  const tick = useCallback((timestamp) => {
    if (!startRef.current) startRef.current = timestamp;
    const elapsed = (timestamp - startRef.current) / 1000;
    if (elapsed >= duration) {
      setTime(duration);
      setPlaying(false);
      return;
    }
    setTime(elapsed);
    rafRef.current = requestAnimationFrame(tick);
  }, [duration]);

  const play = useCallback(() => {
    startRef.current = null;
    setTime(-0.001); // force re-render to 0
    setTimeout(() => {
      setTime(0);
      setPlaying(true);
      rafRef.current = requestAnimationFrame(tick);
    }, 20);
  }, [tick]);

  const restart = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    setPlaying(false);
    play();
  }, [play]);

  useEffect(() => {
    // Auto-play on mount
    play();
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, []);

  const aspect = width / height;

  return (
    <TimelineContext.Provider value={{ time, duration, playing }}>
      <div style={{
        width: "100vw", height: "100vh", background, overflow: "hidden",
        display: "flex", alignItems: "center", justifyContent: "center",
        position: "relative", cursor: "pointer",
      }} onClick={restart}>
        <div style={{
          width: "100%", height: "100%",
          maxWidth: `${100 * aspect}vh`, maxHeight: `${100 / aspect}vw`,
          position: "relative", overflow: "hidden",
          fontSize: `min(${100/height * 100}vh, ${100/width * 100}vw)`,
        }}>
          {children}
        </div>

        {/* Progress bar */}
        <div style={{
          position: "absolute", bottom: 0, left: 0, right: 0, height: 3,
          background: "rgba(255,255,255,0.05)",
        }}>
          <div style={{
            height: "100%", background: "var(--accent, #34d399)",
            width: `${Math.max(0, (time / duration) * 100)}%`,
          }} />
        </div>

        {/* Replay hint when done */}
        {!playing && time >= duration && (
          <div style={{
            position: "absolute", bottom: 20, left: "50%", transform: "translateX(-50%)",
            color: "rgba(255,255,255,0.3)", fontSize: 13, fontFamily: "Geist, sans-serif",
            letterSpacing: "0.05em",
          }}>
            click to replay
          </div>
        )}
      </div>
    </TimelineContext.Provider>
  );
}
