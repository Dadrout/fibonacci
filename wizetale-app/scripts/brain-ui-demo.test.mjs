import assert from 'node:assert/strict'
import test from 'node:test'
import { demoPopoverLeft, demoResetStep } from '../components/brain/brain-demo-state.ts'

test('reset needs two clicks within four seconds; an expired click only rearms', () => {
  const first = demoResetStep(null, 1000)
  assert.deepEqual(first, { reset: false, armedUntil: 5000 })
  assert.deepEqual(demoResetStep(first.armedUntil, 4999), { reset: true, armedUntil: null })
  assert.deepEqual(demoResetStep(first.armedUntil, 5000), { reset: false, armedUntil: 9000 })
  // Background-tab timer throttling cannot leave a stale confirmation actionable.
  assert.deepEqual(demoResetStep(first.armedUntil, 12000), { reset: false, armedUntil: 16000 })
  assert.equal(demoResetStep(null, 2000).reset, false)
})

test('demo disclosure stays inside both gutters on phone and projector widths', () => {
  for (const viewport of [320, 390, 760, 1366, 1920]) {
    for (const desiredWidth of [360, 440]) {
      const width = Math.min(desiredWidth, viewport - 24)
      for (const anchor of [8, 24, 140, viewport - 60]) {
        const left = anchor + demoPopoverLeft(anchor, width, viewport)
        assert.ok(left >= 12)
        assert.ok(left + width <= viewport - 12)
      }
    }
  }
  assert.equal(demoPopoverLeft(100, 360, 1366), 0)
})
