const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')

const file = path.resolve(__dirname, '../lib/student-quiz-result.ts')
const loaded = new Module(file, module)
loaded.filename = file
loaded.paths = Module._nodeModulePaths(path.resolve(__dirname, '..'))
loaded._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, file)
const { parseQuizResult } = loaded.exports

const options = [['a', 'b'], ['x', 'y']]

test('a not-yet-submitted quiz result restores as null', () => {
  assert.equal(parseQuizResult({ result: null }, options), null)
})

test('a saved quiz result restores validated answers and score', () => {
  assert.deepEqual(parseQuizResult({ result: { answers: { '1': 'b', '2': 'x' }, score: 1, total: 2 } }, options), {
    answers: { '1': 'b', '2': 'x' }, score: 1, total: 2,
  })
})

test('a quiz result with answers outside the current quiz is rejected', () => {
  assert.throws(() => parseQuizResult({ result: { answers: { '1': 'other', '2': 'x' }, score: 1, total: 2 } }, options))
})

test('a result with a mismatched total or answer set is rejected', () => {
  assert.throws(() => parseQuizResult({ result: { answers: { '1': 'a' }, score: 1, total: 1 } }, options))
})
