const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const root = path.resolve(__dirname, '..')
const read = file => fs.readFileSync(path.join(root, file), 'utf8')

test('student workspace offers clear route navigation with active page semantics', () => {
  const workspace = read('app/create/student-workspace-client.tsx')
  assert.match(workspace, /usePathname/)
  for (const route of ['/create', '/study', '/history']) assert.match(workspace, new RegExp(`href=["']${route}["']`))
  assert.match(workspace, /aria-current=\{activeNav===/)
})

test('story result routes keep Create selected in student navigation', () => {
  const workspace = read('app/create/student-workspace-client.tsx')
  assert.match(workspace, /pathname\.startsWith\('\/story\/'\)/)
  assert.match(workspace, /activeNav.*\/create/)
})

test('study library is fetched only after the study workspace or library is opened', () => {
  const study = read('app/create/study-workspace.tsx')
  assert.match(study, /if\s*\(!active\s*&&\s*!showLibrary\)\s*return/)
  assert.match(study, /didLoad|libraryLoaded/)
})

test('story result heading can show its title or topic without exposing the task id', () => {
  const viewer = read('app/create/story-viewer.tsx')
  assert.match(viewer, /workspace\.setup\.topic\.trim\(\)/)
  assert.doesNotMatch(viewer, /<p[^>]*>\s*\{jobId\}\s*<\/p>/)
})

test('student styles use shared workspace tokens and do not reference undefined prep colors', () => {
  const styles = read('app/create/student-workspace.css')
  for (const token of ['--prep-muted', '--prep-line', '--prep-paper']) assert.doesNotMatch(styles, new RegExp(`var\\(${token}\\)`))
  assert.match(styles, /background:\s*var\(--workspace-canvas\)/)
  assert.match(styles, /var\(--workspace-role-accent\)/)
})

test('story settings copy no longer asks students to repeat shared topic setup', () => {
  const dashboard = read('app/create/dashboard-client.tsx')
  const copy = read('lib/copy.ts')
  assert.match(dashboard, /Set the audience, length, and narration for your story\./)
  assert.doesNotMatch(dashboard, /Choose a subject, then add the question on your mind\./)
  assert.match(copy, /"Set the audience, length, and narration for your story\.": \["Настройте возраст, длительность и озвучивание истории\.", "Жас аралығын, әңгіме ұзақтығын және дыбыстауын баптаңыз\."\]/)
})
