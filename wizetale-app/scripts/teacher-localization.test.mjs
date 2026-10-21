import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { localizedCopy, copyText } from '../lib/copy.ts'

test('interface copy has both translations and preserves template fields', () => {
  for (const [english, pair] of Object.entries(localizedCopy)) {
    assert.equal(pair.length, 2, english)
    for (const translated of pair) {
      assert.ok(translated.trim(), english)
      for (const field of english.match(/\{\w+\}/g) || []) assert.ok(translated.includes(field), `${english}: ${field}`)
    }
    assert.equal(copyText(english, 'en'), english)
    assert.equal(copyText(english, 'ru'), pair[0])
    assert.equal(copyText(english, 'kk'), pair[1])
  }
})
test('teacher screens translate every explicit static copy lookup', () => {
  const paths=['app/teacher/sources/page.tsx','components/teacher/source-picker.tsx','components/teacher/source-references.tsx','app/teacher/page.tsx','app/teacher/lessons/[lessonId]/page.tsx','components/teacher/lesson-form.tsx','components/teacher/resource-editor.tsx','components/teacher/resource-document.tsx','components/teacher/shell.tsx']
  for(const path of paths) {
    const source=readFileSync(new URL(`../${path}`,import.meta.url),'utf8')
    for(const match of source.matchAll(/\bc\(['"]([^'"]+)['"]\)/g)) assert.ok(localizedCopy[match[1]], `${path}: ${match[1]}`)
  }
})
