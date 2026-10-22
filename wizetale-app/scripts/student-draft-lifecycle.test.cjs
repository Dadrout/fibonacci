const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')

const originalFetch = global.fetch
const sampleScript = {
  title: 'Silk Road',
  hook: 'A route linked worlds.',
  sections: [],
  full_narration: 'Trade connected people.',
  estimated_duration_sec: 60,
}

function hookHarness() {
  const state = []
  const refs = []
  let stateIndex = 0
  let refIndex = 0
  const storage = new Map()
  global.window = {
    localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
  }

  const react = {
    useState(initial) {
      const index = stateIndex++
      if (!(index in state)) state[index] = initial
      return [state[index], value => {
        state[index] = typeof value === 'function' ? value(state[index]) : value
      }]
    },
    useRef(initial) {
      const index = refIndex++
      refs[index] ??= { current: initial }
      return refs[index]
    },
    useEffect(effect) { effect() },
    useCallback(callback) { return callback },
  }

  const file = path.resolve(__dirname, '../hooks/use-story-generator.ts')
  const loaded = new Module(file, module)
  loaded.filename = file
  loaded.paths = Module._nodeModulePaths(path.resolve(__dirname, '..'))
  const originalRequire = loaded.require.bind(loaded)
  loaded.require = id => {
    if (id === 'react') return react
    if (id === './use-auth') return { useAuth: () => ({ getToken: async () => 'learner-token', user: { id: 'learner-1' } }) }
    if (id === '@/lib/learner-storage') return { learnerStorageKey: (kind, userId) => `fibonacci-current-${kind}:${userId}` }
    if (id === '@/lib/analytics') return { trackEvent() {}, trackConversion() {}, trackFunnelStep() {} }
    return originalRequire(id)
  }
  loaded._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, file)

  return {
    render() {
      stateIndex = 0
      refIndex = 0
      return loaded.exports.useStoryGenerator()
    },
    storage,
  }
}

function jsonResponse(payload, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload }
}

async function createSavedDraft(harness) {
  const draft = {
    id: 'draft-1', status: 'draft', subject: 'history', topic: 'Silk Road',
    grade_band: '13-15', target_duration_sec: 60, language: 'en-US', voice: 'female',
    script: sampleScript, recap: 'Trade connected people.', quiz: { recap: '', quiz: [] },
    sources: [], knowledge_status: 'none',
  }
  global.fetch = async (_url, init) => {
    assert.equal(init.method, 'POST')
    return jsonResponse(draft, 201)
  }
  await harness.render().generateStory({
    subject: 'history', topic: 'Silk Road', grade_band: '13-15',
    target_duration_sec: 60, language: 'en-US', voice: 'female',
  })
  return { draft, generator: harness.render() }
}

test('draft PATCH requests stay ordered and the latest saved script remains current', async t => {
  t.after(() => { global.fetch = originalFetch; delete global.window })
  const harness = hookHarness()
  const { draft, generator } = await createSavedDraft(harness)
  const firstScript = { ...sampleScript, title: 'First edit' }
  const secondScript = { ...sampleScript, title: 'Second edit' }
  const requests = []
  let finishFirst
  global.fetch = async (_url, init) => {
    const body = JSON.parse(init.body)
    requests.push(body.script.title)
    if (body.script.title === 'First edit') {
      return new Promise(resolve => { finishFirst = () => resolve(jsonResponse({ ...draft, script: firstScript })) })
    }
    return jsonResponse({ ...draft, script: secondScript })
  }

  const first = generator.updateDraft(firstScript)
  const second = generator.updateDraft(secondScript)
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(requests, ['First edit'])

  finishFirst()
  await first
  await new Promise(resolve => setImmediate(resolve))
  await second

  assert.deepEqual(requests, ['First edit', 'Second edit'])
  assert.equal(harness.render().draft.script.title, 'Second edit')
})

test('render waits for autosave and submits the latest editor snapshot', async t => {
  t.after(() => { global.fetch = originalFetch; delete global.window })
  const harness = hookHarness()
  const { draft, generator } = await createSavedDraft(harness)
  const autosaved = { ...sampleScript, title: 'Autosaved edit' }
  const rendered = { ...sampleScript, title: 'Final render snapshot' }
  const requests = []
  let finishAutosave
  global.fetch = async (_url, init) => {
    if (init.method === 'POST') {
      requests.push('POST render')
      return jsonResponse({ job_id: 'job-1' }, 202)
    }
    const body = JSON.parse(init.body)
    requests.push(`PATCH ${body.script.title}`)
    if (body.script.title === autosaved.title) {
      return new Promise(resolve => { finishAutosave = () => resolve(jsonResponse({ ...draft, script: autosaved })) })
    }
    return jsonResponse({ ...draft, script: rendered })
  }

  const saving = generator.updateDraft(autosaved)
  await new Promise(resolve => setImmediate(resolve))
  const rendering = generator.renderDraft(rendered)
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(requests, ['PATCH Autosaved edit'])

  finishAutosave()
  await saving
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(requests, [
    'PATCH Autosaved edit',
    'PATCH Final render snapshot',
    'POST render',
  ])
  assert.equal(await rendering, 'job-1')
})

test('flushDraft persists the current editor snapshot before sign-out can continue', async t => {
  t.after(() => { global.fetch = originalFetch; delete global.window })
  const harness = hookHarness()
  const { draft, generator } = await createSavedDraft(harness)
  const latestEdit = { ...sampleScript, title: 'Typed just before sign-out' }
  let finishPatch
  global.fetch = async (_url, init) => {
    assert.equal(init.method, 'PATCH')
    assert.equal(JSON.parse(init.body).script.title, latestEdit.title)
    return new Promise(resolve => { finishPatch = () => resolve(jsonResponse({ ...draft, script: latestEdit })) })
  }

  const flushing = generator.flushDraft(latestEdit)
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(typeof finishPatch, 'function')

  finishPatch()
  assert.equal(await flushing, true)
  assert.equal(harness.render().draft.script.title, latestEdit.title)
})

test('flushDraft blocks sign-out when the latest script cannot be saved', async t => {
  t.after(() => { global.fetch = originalFetch; delete global.window })
  const harness = hookHarness()
  const { draft, generator } = await createSavedDraft(harness)
  const latestEdit = { ...sampleScript, title: 'Keep me on screen' }
  global.fetch = async () => jsonResponse({ detail: 'Temporary save failure' }, 503)

  assert.equal(await generator.flushDraft(latestEdit), false)
  assert.equal(harness.render().draft.script.title, draft.script.title)
})

test('discard waits for an already queued PATCH before deleting the draft', async t => {
  t.after(() => { global.fetch = originalFetch; delete global.window })
  const harness = hookHarness()
  const { draft, generator } = await createSavedDraft(harness)
  const requests = []
  let finishPatch
  let finishDelete
  global.fetch = async (_url, init) => {
    requests.push(init.method)
    if (init.method === 'PATCH') {
      return new Promise(resolve => { finishPatch = () => resolve(jsonResponse({ ...draft, script: { ...sampleScript, title: 'Latest edit' } })) })
    }
    return new Promise(resolve => { finishDelete = () => resolve({ ok: true, status: 204, json: async () => { throw new Error('No content') } }) })
  }

  const saving = generator.updateDraft({ ...sampleScript, title: 'Latest edit' })
  await new Promise(resolve => setImmediate(resolve))
  const discarding = typeof generator.discardDraft === 'function'
    ? generator.discardDraft()
    : Promise.resolve(false)
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(requests, ['PATCH'])

  finishPatch()
  await saving
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(requests, ['PATCH', 'DELETE'])
  finishDelete()
  assert.equal(await discarding, true)
})

test('discard removes the owned server draft and its active local pointer', async t => {
  t.after(() => { global.fetch = originalFetch; delete global.window })
  const harness = hookHarness()
  await createSavedDraft(harness)
  const calls = []
  global.fetch = async (url, init) => {
    calls.push([url, init.method])
    return { ok: true, status: 204, json: async () => { throw new Error('No content') } }
  }

  const discarded = await harness.render().discardDraft()

  assert.equal(discarded, true)
  assert.deepEqual(calls, [['/api/v1/story-drafts/draft-1', 'DELETE']])
  assert.equal(harness.render().draft, null)
  assert.equal(harness.storage.has('fibonacci-current-draft:learner-1'), false)
})

test('clearing the active pointer keeps a saved server draft available', async t => {
  t.after(() => { global.fetch = originalFetch; delete global.window })
  const harness = hookHarness()
  const { draft, generator } = await createSavedDraft(harness)
  let laterRequests = 0
  global.fetch = async () => { laterRequests += 1; return jsonResponse({}) }

  generator.clearDraft()

  assert.equal(laterRequests, 0)
  assert.equal(harness.render().draft, null)
  assert.equal(harness.storage.has('fibonacci-current-draft:learner-1'), false)
  assert.equal(draft.status, 'draft')
})

test('discard conflict keeps the editable workspace and active pointer', async t => {
  t.after(() => { global.fetch = originalFetch; delete global.window })
  const harness = hookHarness()
  const { draft } = await createSavedDraft(harness)
  global.fetch = async () => jsonResponse({ detail: 'This draft can no longer be discarded' }, 409)

  const discarded = await harness.render().discardDraft()

  assert.equal(discarded, false)
  assert.equal(harness.render().draft.id, draft.id)
  assert.equal(harness.storage.get('fibonacci-current-draft:learner-1'), draft.id)
})
