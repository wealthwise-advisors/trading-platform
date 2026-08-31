/**
 * The three illustrations on the welcome screen.
 *
 * Each one DEMONSTRATES the step it sits above rather than decorating it: the
 * equity curve draws itself the way a backtest fills in, the candles arrive one
 * at a time the way replay steps through them, and the rows leave the page the
 * way an export does. That is the whole justification for animating here --
 * motion that shows what the feature does is teaching; motion that reacts to
 * the cursor is noise, and was rightly rejected on the sign-in card.
 *
 * Inline SVG, no images. Three reasons: it inherits the theme's colours
 * instead of baking them into a PNG that would be wrong the moment a token
 * changes, it scales to any size without a second asset, and it costs the
 * bundle a few hundred bytes rather than a network round trip on a screen
 * people see once.
 *
 * Every animation is `stroke-dashoffset`, `opacity` or `transform` -- all
 * compositor properties -- so none of this can trigger layout while the app is
 * still starting up behind it.
 */
import { motion, useReducedMotion } from "framer-motion"

const VIOLET = "#9b8afb"
const VIOLET_DEEP = "#7c6cf5"
const RISE = "#34d399"
const FALL = "#f87171"

/** Shared frame: a rounded panel the drawings sit inside. */
function Frame({ children }: { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 240 120" width="100%" height="120"
         preserveAspectRatio="xMidYMid meet"
         style={{ display: "block", height: 120 }}
         role="presentation" aria-hidden>
      <defs>
        <linearGradient id="ob-fade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={VIOLET} stopOpacity="0.20" />
          <stop offset="100%" stopColor={VIOLET} stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Faint grid, so the plots read as charts rather than free-floating lines. */}
      {[24, 48, 72, 96].map((y) => (
        <line key={y} x1="8" y1={y} x2="232" y2={y}
              stroke="rgba(255,255,255,.05)" strokeWidth="1" />
      ))}
      {children}
    </svg>
  )
}

/** Step 1 — an equity curve drawing itself, the way a backtest fills in. */
export function BacktestArt() {
  const still = useReducedMotion()
  const d = "M12,96 L40,84 L64,88 L88,64 L112,70 L136,46 L160,52 L188,28 L228,18"
  return (
    <Frame>
      <motion.path
        d={`${d} L228,112 L12,112 Z`}
        fill="url(#ob-fade)"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: still ? 0 : 1.0, duration: still ? 0 : 0.5 }}
      />
      <motion.path
        d={d}
        fill="none" stroke={RISE} strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round"
        initial={{ pathLength: still ? 1 : 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: still ? 0 : 1.2, ease: "easeInOut" }}
      />
      {/* The endpoint, arriving as the line reaches it. */}
      <motion.circle
        cx="228" cy="18" r="4" fill={RISE}
        initial={{ scale: still ? 1 : 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: still ? 0 : 1.15, type: "spring", bounce: 0.4 }}
      />
    </Frame>
  )
}

/** Step 2 — candles arriving one at a time, the way replay steps through them. */
export function ReplayArt() {
  const still = useReducedMotion()
  const bars = [
    { x: 20, o: 82, c: 68, h: 62, l: 88 }, { x: 44, o: 68, c: 74, h: 62, l: 80 },
    { x: 68, o: 74, c: 56, h: 50, l: 78 }, { x: 92, o: 56, c: 62, h: 50, l: 68 },
    { x: 116, o: 62, c: 44, h: 38, l: 66 }, { x: 140, o: 44, c: 50, h: 38, l: 56 },
    { x: 164, o: 50, c: 32, h: 26, l: 54 }, { x: 188, o: 32, c: 38, h: 26, l: 44 },
    { x: 212, o: 38, c: 22, h: 16, l: 42 },
  ]
  return (
    <Frame>
      {bars.map((b, i) => {
        const up = b.c < b.o                       // lower y is a higher price
        const colour = up ? RISE : FALL
        return (
          <motion.g
            key={b.x}
            initial={{ opacity: still ? 1 : 0, y: still ? 0 : 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: still ? 0 : 0.15 + i * 0.11, duration: 0.28 }}
          >
            <line x1={b.x} y1={b.h} x2={b.x} y2={b.l} stroke={colour} strokeWidth="1.5" />
            <rect x={b.x - 4} y={Math.min(b.o, b.c)} width="8"
                  height={Math.max(3, Math.abs(b.c - b.o))} rx="1.5" fill={colour} />
          </motion.g>
        )
      })}
      {/* The playhead, sweeping across as the bars land. */}
      <motion.line
        y1="10" y2="110" stroke={VIOLET} strokeWidth="1.5" strokeDasharray="3 3"
        initial={{ x1: 12, x2: 12, opacity: still ? 0 : 0.9 }}
        animate={{ x1: 224, x2: 224, opacity: 0 }}
        transition={{ duration: still ? 0 : 1.3, ease: "linear" }}
      />
    </Frame>
  )
}

/** Step 3 — rows lifting off the page, the way an export leaves. */
export function ExportArt() {
  const still = useReducedMotion()
  return (
    <Frame>
      <rect x="62" y="18" width="116" height="84" rx="8"
            fill="rgba(255,255,255,.03)" stroke="rgba(255,255,255,.10)" />
      {[0, 1, 2, 3].map((i) => (
        <motion.rect
          key={i}
          x="76" y={34 + i * 16} height="6" rx="3" fill={i === 0 ? VIOLET : "rgba(255,255,255,.22)"}
          initial={{ width: still ? (i === 0 ? 66 : 88) : 0 }}
          animate={{ width: i === 0 ? 66 : 88 }}
          transition={{ delay: still ? 0 : 0.2 + i * 0.12, duration: 0.35 }}
        />
      ))}
      {/* The arrow, once the rows are there. */}
      <motion.g
        initial={{ opacity: still ? 1 : 0, y: still ? 0 : -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: still ? 0 : 0.9, type: "spring", bounce: 0.35 }}
      >
        <circle cx="120" cy="102" r="14" fill={VIOLET_DEEP} />
        <path d="M120,95 L120,108 M114,102 L120,108 L126,102"
              stroke="#fff" strokeWidth="2" strokeLinecap="round"
              strokeLinejoin="round" fill="none" />
      </motion.g>
    </Frame>
  )
}
