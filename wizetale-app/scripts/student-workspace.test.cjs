const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')
const file = path.resolve(__dirname, '../lib/student-workspace.ts')
const loaded = new Module(file, module)
loaded.filename = file
loaded.paths = Module._nodeModulePaths(path.resolve(__dirname, '..'))
if (fs.existsSync(file)) loaded._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, file)
const { resolveStudentEntry, mergeSlideVisuals, studentGenerationContext } = loaded.exports

test('deep links select their format, item, or saved library with safe fallbacks', () => {
  assert.equal(typeof resolveStudentEntry, 'function', 'workspace deep link resolver is missing')
  assert.deepEqual(resolveStudentEntry({mode:'presentation',material:'deck-1'}), {mode:'presentation',materialId:'deck-1',storyId:null,library:false})
  assert.deepEqual(resolveStudentEntry({story:'job-1'}), {mode:'story',materialId:null,storyId:'job-1',library:false})
  assert.deepEqual(resolveStudentEntry({mode:'unknown',library:'1'}), {mode:'story',materialId:null,storyId:null,library:true})
})

test('each shared subject maps to an API subject and keeps topic and language', () => {
  assert.equal(typeof studentGenerationContext, 'function', 'shared study context is missing')
  for(const subject of ['history_social_studies','geography','philosophy','science','math','language_arts']) {
    assert.deepEqual(studentGenerationContext({subject,topic:'  Our question  ',language:'kk-KZ'}, '6'), {subject,topic:'Our question',language:'kk-KZ',grade:'6'})
  }
  assert.equal(studentGenerationContext({subject:'history',topic:'Topic',language:'en-US'},'6').subject,'history_social_studies')
  assert.equal(studentGenerationContext({subject:'literature',topic:'Topic',language:'en-US'},'6').subject,'language_arts')
  assert.throws(()=>studentGenerationContext({subject:'invalid',topic:'Topic',language:'en-US'}, '6'))
})

test('visual refresh preserves unsaved slide text and removes visuals removed on the server', () => {
  assert.equal(typeof mergeSlideVisuals, 'function', 'visual reconciliation is missing')
  const edited=[{title:'My unsaved title',key_points:['Edited'],speaker_notes:'Notes',visual:{status:'failed'}},{title:'Second',visual:{status:'ready'}}]
  const updated=[{title:'Server title',visual:{status:'ready',kind:'image',image_url:'https://example.test/image.png',alt_text:'Volcano',caption:'Volcano'}},{title:'Second'}]
  const merged=mergeSlideVisuals(edited,updated)
  assert.equal(merged[0].title,'My unsaved title')
  assert.deepEqual(merged[0].key_points,['Edited'])
  assert.equal(merged[0].visual.status,'ready')
  assert.equal(merged[1].visual,undefined)
  assert.equal(edited[0].visual.status,'failed')
})
