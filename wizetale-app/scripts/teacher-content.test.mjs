import assert from 'node:assert/strict'
import test from 'node:test'
import { existsSync } from 'node:fs'
const url = new URL('../lib/teacher-content.ts', import.meta.url)
async function contentTools() {
  assert.ok(existsSync(url), 'Teacher resource rendering helpers are missing')
  return import(url)
}
const source = {title:'Fractions',instructions:'Answer',objectives:[],sections:[],questions:[{prompt:'A',choices:[],points:1},{prompt:'B',choices:[],points:1},{prompt:'C',choices:[],points:1}],flashcards:[{front:'Fraction',back:'Part of a whole'}],answer_key:[{question_number:1,answer:'A',explanation:''},{question_number:2,answer:'B',explanation:''},{question_number:3,answer:'C',explanation:''}],teacher_notes:[{heading:'Rubric',body:'Award 1 point'}],duration_minutes:45}
test('student printing excludes answer keys and teacher notes without changing saved content', async () => {
  const { printableContent } = await contentTools()
  const printed = printableContent(source, 'student')
  assert.deepEqual(printed.answer_key, [])
  assert.deepEqual(printed.teacher_notes, [])
  assert.equal(source.answer_key.length, 3)
  assert.equal(printed.questions.length, 3)
  assert.equal(printableContent(source, 'teacher').answer_key.length, 3)
})
test('flashcard backs remain printable learning material', async () => {
  const { printableContent } = await contentTools()
  assert.equal(printableContent(source, 'student').flashcards[0].back, 'Part of a whole')
})
test('removing a question keeps answer numbering matched', async () => {
  const { removeQuestion } = await contentTools()
  const result = removeQuestion(source,1)
  assert.deepEqual(result.questions.map(q=>q.prompt), ['A','C'])
  assert.deepEqual(result.answer_key.map(a=>[a.question_number,a.answer]), [[1,'A'],[2,'C']])
  assert.equal(source.questions.length, 3)
})
test('visual progress does not mark edited lesson text as dirty', async () => {
  const { editableResourceContent } = await contentTools()
  const content = {...source, slides:[{title:'Halves',key_points:['Two equal parts'],speaker_notes:'Explain a half',visual:{status:'pending',kind:'diagram',alt_text:'',caption:'',image_url:null}}]}
  const refreshed = {...content, slides:[{...content.slides[0],visual:{status:'ready',kind:'diagram',alt_text:'Two equal parts of a circle',caption:'One half',image_url:'https://example.test/half.png'}}]}
  assert.deepEqual(editableResourceContent(content), editableResourceContent(refreshed))
  assert.equal(editableResourceContent(content).slides[0].visual, undefined)
})
test('refreshed visuals keep unsaved slide text while adopting the latest image', async () => {
  const { mergeSlideVisuals } = await contentTools()
  const draft = {...source, slides:[{title:'My edited title',key_points:['An edited point'],speaker_notes:'My notes',visual:{status:'pending',kind:'diagram',alt_text:'',caption:'',image_url:null}}]}
  const server = {...source, slides:[{title:'Original title',key_points:['Old point'],speaker_notes:'Old notes',visual:{status:'ready',kind:'diagram',alt_text:'A diagram',caption:'A half',image_url:'https://example.test/half.png'}}]}
  const merged = mergeSlideVisuals(draft, server)
  assert.equal(merged.slides[0].title, 'My edited title')
  assert.deepEqual(merged.slides[0].key_points, ['An edited point'])
  assert.equal(merged.slides[0].visual.image_url, 'https://example.test/half.png')
  assert.equal(draft.slides[0].visual.status, 'pending')
})
test('removing a visual on the server clears it from the open draft', async () => {
  const { mergeSlideVisuals } = await contentTools()
  const draft = {...source, slides:[{title:'Edited',key_points:['A'],speaker_notes:'B',visual:{status:'ready',kind:'image',alt_text:'Image',caption:'',image_url:'https://example.test/image.png'}}]}
  const server = {...source, slides:[{title:'Saved',key_points:['A'],speaker_notes:'B'}]}
  assert.equal(mergeSlideVisuals(draft, server).slides[0].visual, undefined)
})
