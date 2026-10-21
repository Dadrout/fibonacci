const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')

const file = path.resolve(__dirname, '../lib/student-history-state.ts')
const loaded = new Module(file, module)
loaded.filename = file
loaded.paths = Module._nodeModulePaths(path.resolve(__dirname, '..'))
loaded._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, file)
const { initialStoryHistoryState, reduceStoryHistory } = loaded.exports

const firstPageStory = { id: 'story-1', task_id: 'job-1' }
const nextPageStory = { id: 'story-2', task_id: 'job-2' }

test('initial load errors remain distinct until a retry succeeds', () => {
  const failed = reduceStoryHistory(initialStoryHistoryState, { type: 'initialFailed', error: 'offline' })
  assert.equal(failed.initialError, 'offline')
  const retrying = reduceStoryHistory(failed, { type: 'initialStarted' })
  assert.equal(retrying.busy, true)
  assert.equal(retrying.initialError, null)
  const loaded = reduceStoryHistory(retrying, { type: 'initialSucceeded', stories: [], hasMore: false })
  assert.equal(loaded.busy, false)
  assert.equal(loaded.initialError, null)
  assert.deepEqual(loaded.stories, [])
})

test('append errors keep current stories and preserve the failed offset for retry', () => {
  const initial = reduceStoryHistory(initialStoryHistoryState, {
    type: 'initialSucceeded', stories: [firstPageStory], hasMore: true,
  })
  const loading = reduceStoryHistory(initial, { type: 'appendStarted' })
  const failed = reduceStoryHistory(loading, { type: 'appendFailed', error: 'offline', offset: 25 })
  assert.deepEqual(failed.stories, [firstPageStory])
  assert.equal(failed.moreError, 'offline')
  assert.equal(failed.retryOffset, 25)
  assert.equal(failed.hasMore, true)
  assert.equal(failed.loadingMore, false)
})

test('retry clears the append error and adds the recovered page once', () => {
  const state = {
    ...initialStoryHistoryState,
    stories: [firstPageStory],
    hasMore: true,
    retryOffset: 25,
    moreError: 'offline',
  }
  const retrying = reduceStoryHistory(state, { type: 'appendStarted' })
  const loaded = reduceStoryHistory(retrying, {
    type: 'appendSucceeded', stories: [nextPageStory], hasMore: false,
  })
  assert.deepEqual(loaded.stories, [firstPageStory, nextPageStory])
  assert.equal(loaded.moreError, null)
  assert.equal(loaded.retryOffset, null)
  assert.equal(loaded.hasMore, false)
  assert.equal(loaded.loadingMore, false)
})

test('a recovered page does not duplicate a story already on the shelf', () => {
  const initial = reduceStoryHistory(initialStoryHistoryState, {
    type: 'initialSucceeded', stories: [firstPageStory], hasMore: true,
  })
  const loaded = reduceStoryHistory(initial, {
    type: 'appendSucceeded', stories: [firstPageStory, nextPageStory], hasMore: false,
  })
  assert.deepEqual(loaded.stories, [firstPageStory, nextPageStory])
})
