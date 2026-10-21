const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const root = path.resolve(__dirname, '..')
const read = file => fs.readFileSync(path.join(root, file), 'utf8')

test('teacher navigation exposes the active route accessibly', () => {
  const shell = read('components/teacher/shell.tsx')
  assert.match(shell, /usePathname/)
  assert.match(shell, /aria-current=\{active\(/)
})

test('teacher styles use one semantic workspace base with a role-aware button foreground', () => {
  const css = read('app/teacher/teacher.css')
  const globalStyles = read('app/globals.css')
  const shellRules = [...css.matchAll(/\.prep-shell\s*\{([^}]*)\}/gs)].map(match => match[1])
  assert.equal(shellRules.filter(rule => /background:\s*var\(--workspace-canvas\)/.test(rule)).length, 1)
  assert.doesNotMatch(css, /--ts-|hsl\(var\(--(?:background|foreground|card|border|primary|ring)\)\)/)
  assert.match(css, /color:\s*var\(--workspace-role-on-accent\)/)
  assert.match(globalStyles, /--workspace-role-on-accent:\s*var\(--workspace-teacher-accent-foreground\)/)
  const darkTheme = globalStyles.match(/\.dark\s*\{([^}]*)\}/s)?.[1] || ''
  assert.match(darkTheme, /--workspace-teacher-accent-foreground:\s*var\(--studio-on-green\)/i)
})

test('source library distinguishes loading, empty, and failed states and guides text length', () => {
  const page = read('app/teacher/sources/page.tsx')
  assert.match(page, /sourcesLoading/)
  assert.match(page, /role="status"/)
  assert.match(page, /role="alert"/)
  assert.match(page, /text\.length/)
  assert.match(page, /200,000/)
})

test('teacher source and lesson flows explain the preparation sequence', () => {
  const lesson = read('app/teacher/lessons/[lessonId]/page.tsx')
  assert.match(lesson, /prep-steps/)
  assert.match(lesson, /aria-current=\{!selected \? 'step'/)
  assert.match(lesson, /prep-resources-empty/)
  const home = read('app/teacher/page.tsx')
  assert.match(home, /Create your first lesson/)
})

test('lesson fields lock during saves and resource removal names its item', () => {
  const form = read('components/teacher/lesson-form.tsx')
  assert.match(form, /disabled=\{busy\}/)
  const editor = read('components/teacher/resource-editor.tsx')
  assert.match(editor, /c\('Remove section'\)/)
  assert.match(editor, /c\('Remove objective'\)/)
  assert.match(editor, /c\('Remove question'\)/)
  assert.match(editor, /c\('Remove flashcard'\)/)
})

test('teacher hover movement honors reduced motion and mobile resources do not nest-scroll', () => {
  const css = read('app/teacher/teacher.css')
  assert.match(css, /prefers-reduced-motion:\s*reduce[^}]*\.prep-button:hover[^}]*transform:\s*none/s)
  assert.match(css, /\.prep-resource-list\s*\{\s*position:\s*static;\s*max-height:\s*none;\s*overflow:\s*visible;?\s*\}/)
})

test('lesson source picker distinguishes loading and empty libraries with a recovery path', () => {
  const picker = read('components/teacher/source-picker.tsx')
  assert.match(picker, /loadingSources/)
  assert.match(picker, /role=\"status\"/)
  assert.match(picker, /role=\"alert\"/)
  assert.match(picker, /No ready sources yet/)
})
