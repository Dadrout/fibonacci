const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const globalStyles = fs.readFileSync(path.join(root, 'app/globals.css'), 'utf8')
const studentStyles = fs.readFileSync(path.join(root, 'app/create/student-workspace.css'), 'utf8')

test('workspace design tokens define both role accents for light and dark themes', () => {
  for (const token of [
    '--workspace-canvas',
    '--workspace-surface',
    '--workspace-ink',
    '--workspace-muted',
    '--workspace-line',
    '--workspace-primary',
    '--workspace-student-accent',
    '--workspace-student-soft',
    '--workspace-teacher-accent',
    '--workspace-teacher-soft',
  ]) {
    assert.match(globalStyles, new RegExp(`${token}\\s*:`), `${token} needs a light theme value`)
  }

  const darkTheme = globalStyles.match(/\.dark\s*\{([^}]*)\}/s)?.[1] || ''
  for (const token of ['--workspace-canvas', '--workspace-surface', '--workspace-ink', '--workspace-muted', '--workspace-line']) {
    assert.match(darkTheme, new RegExp(`${token}\\s*:`), `${token} needs a dark theme value`)
  }
})

test('student workspace styles do not depend on undefined legacy prep tokens', () => {
  for (const token of ['--prep-muted', '--prep-line', '--prep-paper']) {
    assert.doesNotMatch(studentStyles, new RegExp(`var\\(${token}\\)`), `${token} is not defined by the shared workspace system`)
  }
})
