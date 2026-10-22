import assert from 'node:assert/strict'
import test from 'node:test'
import { formatBrainDate, setKazakhSupportForTests } from '../components/brain/brain-date.ts'

const at = new Date('2026-10-22T10:05:00Z')

test('Kazakh dates stay Kazakh when the browser has no Kazakh date data', () => {
  setKazakhSupportForTests(false)
  try {
    assert.equal(formatBrainDate(at, 'kk', { month: 'short', day: 'numeric', timeZone: 'UTC' }), '22 қаз.')
    assert.equal(formatBrainDate(at, 'kk-KZ', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' }), '22 қаз., бс')
    assert.equal(formatBrainDate(at, 'kk', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }), '22 қаз., 10:05')
    assert.equal(formatBrainDate(at, 'kk', { timeZone: 'UTC' }), '22.10.2026')
  } finally {
    setKazakhSupportForTests(null)
  }
})

test('other languages and browsers with Kazakh data use Intl', () => {
  setKazakhSupportForTests(true)
  try {
    const options = { month: 'short', day: 'numeric', timeZone: 'UTC' }
    assert.equal(formatBrainDate(at, 'kk', options), new Intl.DateTimeFormat('kk', options).format(at))
    assert.equal(formatBrainDate(at, 'ru', options), new Intl.DateTimeFormat('ru', options).format(at))
    assert.equal(formatBrainDate(at, 'en', options), 'Oct 22')
    assert.equal(formatBrainDate(new Date('nope'), 'en', options), '')
  } finally {
    setKazakhSupportForTests(null)
  }
})
