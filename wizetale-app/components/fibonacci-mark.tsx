// Fibonacci seedhead mark. Seeds sit on the golden angle (~137.5°), the
// arrangement a sunflower uses, and grow from the centre outwards like a real
// seedhead. The first (centre) seed is the gold "spark". `filled` lets the mark
// double as a progress display: seeds past that count are drawn as outlines.
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5))

type FibonacciMarkProps = {
  size?: number
  seeds?: number
  filled?: number
  className?: string
  label?: string
  /** Hide the gold centre seed (for one-colour uses). */
  plain?: boolean
}

export function seedPositions(seeds: number) {
  const spread = 40 / Math.sqrt(seeds)
  return Array.from({ length: seeds }, (_, index) => {
    const t = Math.sqrt((index + 0.6) / seeds)
    const radius = spread * Math.sqrt(index + 0.6)
    const angle = index * GOLDEN_ANGLE
    return {
      x: +(radius * Math.cos(angle)).toFixed(2),
      y: +(radius * Math.sin(angle)).toFixed(2),
      // Small seeds in the middle, larger at the rim.
      r: +((0.55 + 0.6 * t) * spread * 0.8).toFixed(2),
    }
  })
}

export function FibonacciMark({ size = 36, seeds = 21, filled, className, label, plain = false }: FibonacciMarkProps) {
  const count = size < 24 ? Math.min(seeds, 8) : seeds
  const done = filled ?? count
  return (
    <svg
      className={['fibonacci-mark', className].filter(Boolean).join(' ')}
      width={size}
      height={size}
      viewBox="-50 -50 100 100"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      {seedPositions(count).map((seed, index) => (
        <circle
          key={index}
          cx={seed.x}
          cy={seed.y}
          r={seed.r}
          className={[
            'fibonacci-seed',
            index < done ? 'is-filled' : '',
            index === 0 && !plain ? 'is-spark' : '',
          ].filter(Boolean).join(' ')}
        />
      ))}
    </svg>
  )
}

/** Mark plus lowercase wordmark, used in every header. */
export function FibonacciLogo({ size = 30, className }: { size?: number; className?: string }) {
  return (
    <span className={['fibonacci-logo', className].filter(Boolean).join(' ')}>
      <FibonacciMark size={size} />
      <span className="fibonacci-wordmark">fibonacci</span>
    </span>
  )
}
