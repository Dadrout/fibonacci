const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')

test('the shared learning workspace gates private story and study views by learner identity', () => {
  const workspace = read('app/create/student-workspace-client.tsx')
  assert.match(workspace, /if\(!isPreview&&!user\)return <SignInPrompt/)
  assert.match(workspace, /<LearningWorkspace key=\{isPreview\?'preview':user!\.id\}/)
  assert.match(workspace, /<StoryViewer key=\{storyId\}/)
  assert.match(workspace, /<StudyWorkspace active=/)
})

test('history and legacy story URLs open the shared learning workspace', () => {
  assert.match(read('app/history/page.tsx'), /StudentWorkspace/)
  assert.match(read('app/story/[taskId]/page.tsx'), /StudentWorkspace/)
  assert.match(read('app/story/[taskId]/page.tsx'), /storyId:\s*taskId/)
})

test('story polling stays inside the authenticated shared workspace', () => {
  const workspace = read('app/create/student-workspace-client.tsx')
  const viewer = read('app/create/story-viewer.tsx')
  assert.match(workspace, /if\(!isPreview&&!user\)return <SignInPrompt/)
  assert.match(workspace, /<StoryViewer key=\{storyId\} jobId=\{storyId\}/)
  assert.match(viewer, /useStoryPoller\(jobId\)/)
})
