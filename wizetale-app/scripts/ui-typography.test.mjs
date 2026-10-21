import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => readFileSync(path.join(appRoot, relativePath), 'utf8')
const matches = (value, pattern, message) => assert.ok(pattern.test(value), message)

test('Literata and GolosText are bundled with their open font licenses', () => {
  for (const asset of [
    'public/fonts/Literata-Variable.ttf',
    'public/fonts/GolosText-Variable.ttf',
  ]) {
    assert.ok(existsSync(path.join(appRoot, asset)), `${asset} should exist`)
  }

  for (const license of ['Literata-OFL.txt', 'GolosText-OFL.txt']) {
    const contents = read(`public/fonts/${license}`)
    matches(contents, /SIL OPEN FONT LICENSE/i, `${license} should contain the SIL OFL`)
  }
})

test('the root layout loads both font families locally and applies their variables', () => {
  const layout = read('app/layout.tsx')

  matches(layout, /localFont/, 'root layout should use next/font/local')
  matches(layout, /Literata-Variable\.ttf/, 'root layout should load Literata locally')
  matches(layout, /GolosText-Variable\.ttf/, 'root layout should load GolosText locally')
  matches(layout, /literata\.variable/, 'root body should receive the heading font variable')
  matches(layout, /golos\.variable/, 'root body should receive the body font variable')
})

test('global styles define the shared font variables and both theme palettes', () => {
  const styles = read('app/globals.css')

  matches(styles, /--font-heading\s*:/, 'shared heading font variable should be defined')
  matches(styles, /--font-body\s*:/, 'shared body font variable should be defined')
  matches(styles, /font-family:\s*var\(--font-body\)/, 'body should use the shared reading font')
  matches(styles, /font-family:\s*var\(--font-heading\)/, 'headings should use the shared display font')
  matches(styles, /\.dark\s*\{/, 'dark theme tokens should be defined')
  matches(styles, /--ts-paper\s*:/, 'paper surface token should be defined')
  matches(styles, /--ts-ink\s*:/, 'ink text token should be defined')
})

test('home and create routes do not load a second copy of Inter', () => {
  assert.doesNotMatch(read('app/page.tsx'), /localFont|InterVariable/)
  assert.doesNotMatch(read('app/create/page.tsx'), /localFont|InterVariable/)
})

test('landing and workspace use shared typography and keep dark theme surfaces', () => {
  const landing = read('app/landing/globals.css')
  const workspace = read('app/globals.css')

  matches(landing, /font-family:\s*var\(--font-body\)/, 'landing body should use the shared reading font')
  matches(landing, /font-family:\s*var\(--font-heading\)/, 'landing headings should use Literata')
  matches(landing, /var\(--studio-paper\)/, 'landing should inherit semantic surfaces')
  matches(workspace, /\.dark\s*\{[^}]*--studio-paper:/s, 'shared surfaces should support dark mode')
  matches(workspace, /font-family:\s*var\(--font-body\)/, 'workspace should use the shared reading font')
  assert.doesNotMatch(workspace, /--font-dashboard-inter/)
})

test('decorative landing motion is disabled for reduced-motion preferences', () => {
  const landing = read('app/landing/globals.css')

  matches(landing, /@media\s*\(prefers-reduced-motion:\s*reduce\)/, 'landing should declare reduced-motion behavior')
  matches(landing, /prefers-reduced-motion:reduce\)[\s\S]*?animation:none/, 'landing motion should stop when reduced motion is preferred')
})

test('the landing uses a responsive content grid without absolute hero decoration', () => {
  const landing = read('app/landing/globals.css')
  matches(landing, /\.field-hero\{[^}]*display:grid/, 'hero content should use a grid')
  matches(landing, /@media\(max-width:650px\)[\s\S]*?\.field-hero\{[^}]*grid-template-columns:1fr/, 'small screens should stack content')
  assert.doesNotMatch(read('components/slush-landing.tsx'), /RibbonArt|slush-ticker|slush-sticker/)
})

test('the workspace intro leaves a gutter between its text and illustration on phones', () => {
  const styles = read('app/globals.css')

  matches(styles, /@media\s*\(max-width:\s*560px\)[\s\S]*?\.dash-intro\s*\{[^}]*column-gap:\s*12px/, 'mobile workspace intro should preserve separation between the copy and sticker')
})

test('shared auth controls use readable text and comfortable touch targets', () => {
  const button = read('components/ui/button.tsx')
  const input = read('components/ui/input.tsx')
  const label = read('components/ui/label.tsx')

  matches(button, /text-base/, 'buttons should use readable base-size text')
  matches(button, /default:\s*"h-11/, 'default buttons should have a 44px target')
  matches(input, /h-11/, 'inputs should have a 44px target')
  matches(input, /text-base/, 'inputs should use readable base-size text')
  assert.doesNotMatch(input, /md:text-sm/)
  matches(label, /text-base/, 'field labels should use readable base-size text')
})

test('auth routes use the shared theme page surface', () => {
  for (const route of [
    'app/login/page.tsx',
    'app/register/page.tsx',
    'app/reset-password/page.tsx',
    'app/reset-password/update/page.tsx',
    'app/verify-email/page.tsx',
  ]) {
    matches(read(route), /auth-page/, `${route} should use the shared auth page surface`)
  }
})

test('legacy story and history URLs share the themed learning workspace', () => {
  for (const route of ['app/history/page.tsx', 'app/story/[taskId]/page.tsx']) {
    const source = read(route)
    matches(source, /StudentWorkspace/, `${route} should open the shared learning workspace`)
    assert.doesNotMatch(source, /dark:bg-slate-950|dark:bg-slate-900/, `${route} should use theme tokens instead of fixed dark colors`)
  }
  const workspace = read('app/create/student-workspace-client.tsx')
  matches(workspace, /app-content-page/, 'the learning workspace should use the shared content page surface')
  matches(workspace, /bg-background/, 'the learning workspace should use the themed page surface')
  matches(workspace, /text-foreground/, 'the learning workspace should use theme-aware text')
})

test('the profile screen keeps the shared theme surfaces and readable copy', () => {
  const route = read('app/profile/page.tsx')
  matches(route, /app-content-page/, 'the profile should use the shared content page surface')
  matches(route, /bg-card/, 'the profile should use the shared card surface')
  matches(route, /text-muted-foreground/, 'the profile should use shared supporting text colors')
  matches(route, /text-base/, 'the profile should keep its primary copy at a readable size')
  assert.doesNotMatch(route, /dark:bg-slate-950|dark:bg-slate-900/)
})

test('account and story actions keep visible keyboard focus', () => {
  const styles = read('app/globals.css')
  matches(styles, /\.app-content-page\s+:is\(a,button,input,textarea,select,summary\):focus-visible/, 'content-page controls should have a visible focus ring')
})
