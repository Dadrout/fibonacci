import assert from 'node:assert/strict'
import test from 'node:test'
import { clampSlideIndex, slideIndexForKey } from '../components/brain/brain-presentation-logic.ts'

test('slide indices stay within the deck, including empty and malformed counts', () => {
  assert.equal(clampSlideIndex(-3, 7), 0)
  assert.equal(clampSlideIndex(99, 7), 6)
  assert.equal(clampSlideIndex(3.9, 7), 3)
  assert.equal(clampSlideIndex(0, 1), 0)
  assert.equal(clampSlideIndex(3, 0), 0)
  assert.equal(clampSlideIndex(3, -1), 0)
  assert.equal(clampSlideIndex(NaN, 7), 0)
  assert.equal(clampSlideIndex(Infinity, 7), 0)
  assert.equal(clampSlideIndex(3, Infinity), 0)
})

test('arrows and Home/End navigate without wrapping at either edge', () => {
  assert.equal(slideIndexForKey('ArrowRight', 2, 7), 3)
  assert.equal(slideIndexForKey('ArrowLeft', 2, 7), 1)
  assert.equal(slideIndexForKey('ArrowLeft', 0, 7), 0)
  assert.equal(slideIndexForKey('ArrowRight', 6, 7), 6)
  assert.equal(slideIndexForKey('Home', 4, 7), 0)
  assert.equal(slideIndexForKey('End', 4, 7), 6)
  assert.equal(slideIndexForKey('ArrowRight', 0, 1), 0)
  assert.equal(slideIndexForKey('ArrowRight', 0, 0), null)
})

test('Space advances only in fullscreen; Escape stays with the browser', () => {
  assert.equal(slideIndexForKey(' ', 2, 7), null)
  assert.equal(slideIndexForKey(' ', 2, 7, { presenting: true }), 3)
  assert.equal(slideIndexForKey(' ', 6, 7, { presenting: true }), 6)
  assert.equal(slideIndexForKey('Escape', 2, 7, { presenting: true }), null)
  assert.equal(slideIndexForKey('Enter', 2, 7), null)
})

test('controls, source dialogs, and modified shortcuts retain their keyboard behavior', () => {
  for (const key of ['ArrowRight', 'ArrowLeft', ' ', 'Home', 'End']) {
    assert.equal(slideIndexForKey(key, 2, 7, { presenting: true, interactive: true }), null)
    assert.equal(slideIndexForKey(key, 2, 7, { modified: true }), null)
  }
})
