/** A fresh click after the deadline must arm reset again, even if a timer was delayed. */
export function demoResetStep(armedUntil: number | null, now: number) {
  return armedUntil !== null && now < armedUntil
    ? { reset: true as const, armedUntil: null }
    : { reset: false as const, armedUntil: now + 4000 }
}

/** Offset relative to the badge, keeping the disclosure inside the viewport gutters. */
export function demoPopoverLeft(anchorLeft: number, width: number, viewportWidth: number) {
  return Math.max(12 - anchorLeft, Math.min(0, viewportWidth - 12 - anchorLeft - width))
}
