// Shared components and hooks for the Hone Workspace

const { useState, useEffect, useRef, useCallback } = React;

function useHoneState() {
  const [snapshot, setSnapshot] = useState(() => window.HoneBridge?.getState?.() || {});
  useEffect(() => {
    const onState = (event) => setSnapshot(event.detail || window.HoneBridge?.getState?.() || {});
    window.addEventListener("hone:state", onState);
    return () => window.removeEventListener("hone:state", onState);
  }, []);
  return snapshot;
}

// ── Hone mark (SVG)
function HoneMark({ size = 28, ink = "var(--ink)", spark = "var(--spark)", breathe = false }) {
  return (
    <svg
      className={"mark-svg" + (breathe ? " mark-breathe" : "")}
      width={size} height={size} viewBox="0 0 64 64"
      aria-hidden="true"
    >
      <rect x="2" y="2" width="60" height="60" rx="14" fill={ink}/>
      <path d="M16 48 L48 16" stroke={spark} strokeWidth="6" strokeLinecap="round"/>
    </svg>
  );
}

// ── 3D tilt hook — gentle perspective tilt following the mouse
function useTilt(ref, { max = 6, scale = 1, glow = true } = {}) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const onMove = (e) => {
      const r = el.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width;
      const y = (e.clientY - r.top) / r.height;
      const ry = (x - 0.5) * max * 2;
      const rx = -(y - 0.5) * max * 2;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        el.style.setProperty('--rx', rx.toFixed(2) + 'deg');
        el.style.setProperty('--ry', ry.toFixed(2) + 'deg');
        if (glow) {
          el.style.setProperty('--mx', (x * 100).toFixed(0) + '%');
          el.style.setProperty('--my', (y * 100).toFixed(0) + '%');
        }
      });
    };
    const onLeave = () => {
      cancelAnimationFrame(raf);
      el.style.setProperty('--rx', '0deg');
      el.style.setProperty('--ry', '0deg');
    };
    el.addEventListener('mousemove', onMove);
    el.addEventListener('mouseleave', onLeave);
    return () => {
      cancelAnimationFrame(raf);
      el.removeEventListener('mousemove', onMove);
      el.removeEventListener('mouseleave', onLeave);
    };
  }, [ref, max, glow]);
}

// ── Count-up animator
function CountUp({ value, duration = 1100, suffix = "", decimals = 0, delay = 0 }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    let raf, start;
    const tick = (t) => {
      if (!start) start = t + delay;
      if (t < start) { raf = requestAnimationFrame(tick); return; }
      const p = Math.min(1, (t - start) / duration);
      const e = 1 - Math.pow(1 - p, 3);
      setV(value * e);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, delay]);
  return <span className="tnum">{v.toFixed(decimals)}{suffix}</span>;
}

const PROCESSING_MESSAGES = [
  "Parsing JD...",
  "Cross-referencing memory...",
  "Refining bullets...",
  "Exporting DOCX...",
  "Preparing preview...",
];

function TerminalStatus({ active, mode = "generating", messages = PROCESSING_MESSAGES }) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (!active) {
      setIndex(0);
      return undefined;
    }
    const id = setInterval(() => setIndex((value) => (value + 1) % messages.length), 1150);
    return () => clearInterval(id);
  }, [active, messages.length]);
  if (!active) return null;
  return (
    <span className="terminal-status" aria-live="polite">
      <span className="terminal-dot"></span>
      <span className="terminal-mode">{mode}</span>
      <span className="terminal-text" key={messages[index]}>{messages[index]}</span>
    </span>
  );
}

// ── Mouse-following ambient glow
function AmbientGlow() {
  const ref = useRef(null);
  useEffect(() => {
    let raf;
    const onMove = (e) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        if (!ref.current) return;
        ref.current.style.transform = `translate(${e.clientX}px, ${e.clientY}px) translate(-50%, -50%)`;
      });
    };
    window.addEventListener('pointermove', onMove);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onMove);
    };
  }, []);
  return <div className="bg-glow" ref={ref}></div>;
}

// ── Strike animation overlay — used when generating
function StrikeOverlay({ show }) {
  const canvasRef = useRef(null);
  useEffect(() => {
    if (!show) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const W = canvas.width = canvas.clientWidth * dpr;
    const H = canvas.height = canvas.clientHeight * dpr;
    let start = 0;
    let raf;
    const particles = [];

    const tick = (t) => {
      if (!start) start = t;
      const dt = 16;
      const elapsed = t - start;

      ctx.clearRect(0, 0, W, H);

      const cx = W / 2, cy = H / 2;
      const len = W * 0.7;

      // streak
      if (elapsed < 500) {
        const p = elapsed / 500;
        const e = 1 - Math.pow(1 - p, 5);
        const axX = 1 / Math.SQRT2, axY = -1 / Math.SQRT2;
        const halfL = len / 2;
        const carveCx = -halfL * axX;
        const carveCy = -halfL * axY;
        const startCx = carveCx - W * 1.0 * axX;
        const startCy = carveCy - W * 1.0 * axY;
        const tx = startCx + (carveCx - startCx) * e;
        const ty = startCy + (carveCy - startCy) * e;
        const ox = cx + tx, oy = cy + ty;
        ctx.save();
        ctx.translate(ox, oy);
        ctx.rotate(-Math.PI / 4);
        const grad = ctx.createLinearGradient(-len/2, 0, len/2, 0);
        grad.addColorStop(0, 'rgba(255,90,31,0)');
        grad.addColorStop(0.4, 'rgba(255,90,31,0.5)');
        grad.addColorStop(0.85, 'rgba(255,200,140,1)');
        grad.addColorStop(1, '#FFF');
        ctx.fillStyle = grad;
        ctx.shadowBlur = 24 * dpr;
        ctx.shadowColor = '#FF5A1F';
        ctx.fillRect(-len/2, -3*dpr, len, 6*dpr);
        ctx.restore();
        // emit trail particles
        if (p > 0.1) {
          const headX = ox + halfL * axX;
          const headY = oy + halfL * axY;
          for (let i = 0; i < 3; i++) {
            const ang = Math.PI * 0.75 + (Math.random() - 0.5) * 0.6;
            const spd = (1.2 + Math.random() * 2.4) * dpr;
            particles.push({
              x: headX, y: headY,
              vx: Math.cos(ang) * spd, vy: Math.sin(ang) * spd,
              life: 400 + Math.random() * 300, max: 700,
              size: (0.9 + Math.random() * 1.2) * dpr,
              color: Math.random() < 0.4 ? [255, 240, 200] : [255, 140, 80],
              drag: 0.93,
            });
          }
        }
      } else if (elapsed < 550) {
        // bloom flash
        const p = (elapsed - 500) / 50;
        const op = 1 - p;
        ctx.save();
        ctx.globalCompositeOperation = 'screen';
        const r = 80 * dpr * (1 + p * 3);
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        g.addColorStop(0, `rgba(255,255,255,${op * 0.9})`);
        g.addColorStop(0.3, `rgba(255,180,128,${op * 0.7})`);
        g.addColorStop(0.7, `rgba(255,90,31,0)`);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
        // big burst
        if (elapsed < 510) {
          for (let i = 0; i < 40; i++) {
            const ang = Math.random() * Math.PI * 2;
            const spd = (1.5 + Math.random() * 4) * dpr;
            particles.push({
              x: cx, y: cy,
              vx: Math.cos(ang) * spd, vy: Math.sin(ang) * spd,
              life: 700 + Math.random() * 300, max: 1000,
              size: (1 + Math.random() * 1.4) * dpr,
              color: Math.random() < 0.35 ? [255, 240, 200] : [255, 120, 60],
              drag: 0.94,
            });
          }
        }
      }

      // update + draw particles
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx * 0.06 * dt; p.y += p.vy * 0.06 * dt;
        p.vx *= p.drag; p.vy *= p.drag;
        p.life -= dt;
        if (p.life <= 0) { particles.splice(i, 1); continue; }
        const tt = p.life / p.max;
        const [cr, cg, cb] = p.color;
        const r = p.size * (0.6 + 0.4 * tt);
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 5);
        g.addColorStop(0, `rgba(${cr},${cg},${cb},${tt * 0.7})`);
        g.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r * 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = `rgba(${cr},${cg},${cb},${tt})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
      }

      if (elapsed < 2400) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [show]);

  return (
    <div className={"gen-overlay" + (show ? " show" : "")}>
      <div className="gen-stage">
        <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }}></canvas>
        <div className="gen-caption">
          Honing<small>Parsing JD · Cross-referencing memory · Refining bullets</small>
        </div>
      </div>
    </div>
  );
}

// ── ScoreRing — small SVG ring around overall number
function ScoreRing({ value }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const [drawn, setDrawn] = useState(0);
  useEffect(() => {
    const id = setTimeout(() => setDrawn(value), 120);
    return () => clearTimeout(id);
  }, [value]);
  return (
    <svg className="score-ring" viewBox="0 0 60 60">
      <circle cx="30" cy="30" r={r} fill="none" stroke="rgba(14,14,12,0.1)" strokeWidth="2"/>
      <circle
        cx="30" cy="30" r={r} fill="none"
        stroke="#FF5A1F" strokeWidth="2" strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c - (drawn / 100) * c}
        transform="rotate(-90 30 30)"
        style={{ transition: 'stroke-dashoffset 1400ms cubic-bezier(0.16,1,0.3,1)' }}
      />
    </svg>
  );
}

// ── Icons (compact set)
const Icon = {
  Search: () => (<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="6" cy="6" r="4.2" stroke="currentColor" strokeWidth="1.5"/><path d="M9.2 9.2 L12 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>),
  Download: () => (<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1.5v8M3.5 6L7 9.5 10.5 6M2 12h10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>),
  Copy: () => (<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="3" y="3" width="8" height="9" rx="1.4" stroke="currentColor" strokeWidth="1.3"/><path d="M5 3V2.3A1 1 0 0 1 6 1.3h4A1.3 1.3 0 0 1 11.3 2.7v6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>),
  Share: () => (<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1.5v8M4 4.5 7 1.5l3 3M2 9v3a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>),
  Spark: () => (<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 12 L12 2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/><circle cx="4" cy="10" r="1.5" fill="currentColor"/></svg>),
  Plus: () => (<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 2v10M2 7h10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>),
  X: () => (<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2 L10 10 M10 2 L2 10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>),
  Chev: () => (<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M3 4.5 L6 7.5 L9 4.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>),
  Folder: () => (<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 4 a1 1 0 0 1 1 -1 H6 l1 1 H11 a1 1 0 0 1 1 1 V10 a1 1 0 0 1 -1 1 H3 a1 1 0 0 1 -1 -1 Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/></svg>),
  History: () => (<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 4 A5 5 0 1 1 2 8 M2 2 V5 H5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/><path d="M7 4 V7 L9 8.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>),
  System: () => (<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="2" y="2" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.2"/><rect x="8" y="2" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.2"/><rect x="2" y="8" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.2"/><rect x="8" y="8" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.2"/></svg>),
  LogOut: () => (<svg width="12" height="12" viewBox="0 0 14 14" fill="none"><path d="M6 2H3a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h3M9 4l3 3-3 3M12 7H6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>),
  Save: () => (<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2.5 2.5h7l2 2v7a1 1 0 0 1-1 1h-8a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1Z" stroke="currentColor" strokeWidth="1.3"/><path d="M4.5 2.5v3h4v-3M4.5 9.5h5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>),
};

Object.assign(window, { HoneMark, CountUp, TerminalStatus, ScoreRing, useTilt, AmbientGlow, StrikeOverlay, Icon, useHoneState });
