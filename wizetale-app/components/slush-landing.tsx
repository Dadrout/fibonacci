'use client'

import Link from 'next/link'
import Image from 'next/image'
import { useState } from 'react'
import { useCopy } from '@/hooks/use-copy'
import { LanguagePicker } from '@/components/language-picker'
import { ThemeToggle } from '@/components/theme-toggle'
import { StudioIcon } from '@/components/studio-icon'
import { FibonacciMark } from '@/components/fibonacci-mark'

const sampleStory = 'Picture a long road with no single starting point. Traders carried silk, spices, and stories between towns. Along the way, ideas traveled too — changing the people who shared them.'
const answers = ['Only silk and spices', 'Goods, ideas, and stories', 'Only people from one country']
const pathIdeas = ['Trade routes', 'Goods and ideas', 'Why it still matters']

function SamplePath() {
  const c = useCopy()
  const [view, setView] = useState('story')
  const [answer, setAnswer] = useState<number | null>(null)
  const complete = answer === 1 ? 3 : 2
  return <article className="field-story" id="story-preview" aria-label={c('Sample learning path')}>
    <div className="field-story-heading"><span>{c('SAMPLE PATH')}</span><span>{c('History')} / {c('Connection')}</span></div>
    <div className="field-path">
      <FibonacciMark size={92} seeds={13} filled={complete === 3 ? 13 : 8} className="field-path-mark" label={c(complete === 3 ? 'All three ideas understood' : 'Two of three ideas understood')}/>
      <ol className="field-path-steps">
        {pathIdeas.map((idea, index) => <li key={idea} className={index < complete ? 'is-done' : 'is-current'} aria-current={index === complete ? 'step' : undefined}>
          <span className="field-path-dot" aria-hidden="true"/>
          <span><small>{c('Idea')} {index + 1}</small>{c(idea)}</span>
        </li>)}
      </ol>
    </div>
    <div className="field-story-body">
      <h2>{c('What connected people along the Silk Road?')}</h2>
      <div className="field-sample-switch" role="group" aria-label={c('Explore the sample')}>
        {(['story', 'recap', 'quiz'] as const).map((item, i) => <button key={item} type="button" aria-pressed={view === item} onClick={() => setView(item)}>{c(['Explanation', 'Key idea', 'Quick check'][i])}</button>)}
      </div>
      <div className="field-sample-content" aria-live="polite">
        {view === 'story' && <p>{c(sampleStory)}</p>}
        {view === 'recap' && <p className="field-key-idea">{c('Trade carried more than goods. It connected people and helped ideas travel across cultures.')}</p>}
        {view === 'quiz' && <div className="field-sample-quiz"><p>{c('What traveled along the Silk Road?')}</p>{answers.map((text, i) => <button type="button" key={text} aria-pressed={answer === i} className={answer === i ? 'is-selected' : ''} onClick={() => setAnswer(i)}>{c(text)}{answer === i && <StudioIcon name="check"/>}</button>)}{answer !== null && <p className="field-answer" role="status">{c(answer === 1 ? 'Exactly. People exchanged goods and shared ideas, knowledge, and stories.' : 'Think beyond objects. People also shared ideas and stories. Try again.')}</p>}</div>}
      </div>
      <div className="field-story-foot"><span>{c('An example, ready to explore.')}</span><span>{c('Answer the check to finish the path.')}<StudioIcon name="arrow"/></span></div>
    </div>
  </article>
}

export default function SlushLanding({ previewEnabled }: { previewEnabled: boolean }) {
  const c = useCopy()
  const [menuOpen, setMenuOpen] = useState(false)
  const startHref = previewEnabled ? '/create?preview=1' : '/register'
  return <div className="field-page slush-page">
    <a href="#main-content" className="studio-skip">{c('Skip to content')}</a>
    <header className="field-header field-width">
      <Link href="/" className="field-brand" aria-label={c('Fibonacci home')}><FibonacciMark size={34}/><span>fibonacci</span></Link>
      <nav className="field-nav" aria-label={c('Main navigation')}><a href="#how-it-works">{c('How it works')}</a><a href="#sources">{c('Your sources')}</a><Link href="/teacher">{c('For teachers')}</Link></nav>
      <div className="field-header-actions"><LanguagePicker/><ThemeToggle/><Link className="field-sign-in" href="/login">{c('Sign in')}</Link><button className="field-menu" type="button" aria-label={c(menuOpen ? 'Close menu' : 'Open menu')} aria-expanded={menuOpen} aria-controls="field-mobile-nav" onClick={() => setMenuOpen(!menuOpen)}><StudioIcon name={menuOpen ? 'close' : 'menu'}/></button></div>
    </header>
    {menuOpen && <nav id="field-mobile-nav" className="field-mobile-nav field-width" aria-label={c('Mobile navigation')}><a href="#how-it-works" onClick={() => setMenuOpen(false)}>{c('How it works')}</a><a href="#sources" onClick={() => setMenuOpen(false)}>{c('Your sources')}</a><Link href="/teacher">{c('For teachers')}</Link><Link href="/login">{c('Sign in')}</Link></nav>}
    <main id="main-content">
      <section className="field-hero field-width">
        <div className="field-hero-copy"><h1>{c('Every topic has a path.')}<br/><em>{c('Follow it to understanding.')}</em></h1><p className="field-lead">{c('Fibonacci breaks big topics into ideas you can follow, one step at a time.')}</p><p className="field-hero-description">{c('Start with a question. Get a clear explanation, the key ideas, and practice that shows what you understood: quizzes, flashcards, presentations, and short videos.')}</p><div className="field-hero-actions"><Link href={startHref} className="field-button">{c('Start learning')}<StudioIcon name="arrow"/></Link><Link className="field-inline-link" href="/teacher/sources">{c('Paste or upload a source')}<StudioIcon name="arrow"/></Link><a className="field-inline-link" href="#story-preview">{c('Explore a sample')}<StudioIcon name="down"/></a></div><div className="field-language-note"><span className="field-small-rule"/>{c('English, Russian, and Kazakh.')}<br/>{c('For students and the teachers who guide them.')}</div></div>
        <SamplePath/>
      </section>
      <div className="field-subjects field-width"><span>{c('Each step builds on the last.')}</span><div><span>{c('History')}</span><span>{c('Geography')}</span><span>{c('People & ideas')}</span></div></div>
      <section className="field-process field-width" id="how-it-works"><div className="field-section-intro"><h2>{c('From “why?”')}<br/><em>{c('to “I get it.”')}</em></h2><p>{c('Learning can start anywhere: a question from class, a place on a map, or a thought that will not leave you alone.')}</p></div><ol className="field-process-list">{[
        ['Bring a question', 'Start with the topic you are curious about, or one from class.', 'question'],
        ['Follow the key ideas', 'Read a clear explanation you can edit, with the big ideas pulled out.', 'edit'],
        ['Check what you understood', 'Quizzes and flashcards show what stuck and what needs another look.', 'book'],
      ].map(([title, description, icon], i) => <li key={title}><span className="field-step-number">0{i + 1}</span><Image className="field-step-art" src={`/illustrations/step-${({question:'question',edit:'ideas',book:'check'} as Record<string,string>)[icon]}.png`} alt="" width={64} height={64}/><div><h3>{c(title)}</h3><p>{c(description)}</p></div><StudioIcon name="arrow"/></li>)}</ol></section>
      <section className="field-sources field-width" id="sources">
        <div className="field-section-intro"><h2>{c('Know where answers')}<br/><em>{c('come from.')}</em></h2><p>{c('Add your own PDF, Word, or text files. Lessons made from them list the page or paragraph each one used. If your sources do not cover a topic, Fibonacci tells you instead of guessing.')}</p><Link href="/teacher/sources" className="field-inline-link">{c('Open your source library')}<StudioIcon name="arrow"/></Link></div>
        <figure className="field-evidence">
          <div className="field-evidence-head"><span>{c('Lesson plan')}</span><span>{c('Source-based')}</span></div>
          <p className="field-evidence-body">{c('Plants capture light energy in the chloroplast and store it as chemical energy in sugar.')}</p>
          <div className="field-evidence-sources"><small>{c('Sources used')}</small>
            <span><StudioIcon name="book"/>{c('Photosynthesis notes.pdf')}<b>{c('Page')} 12</b></span>
            <span><StudioIcon name="book"/>{c('Photosynthesis notes.pdf')}<b>{c('Page')} 14</b></span>
          </div>
          <figcaption>{c('Example. Your own files stay private to your account.')}</figcaption>
        </figure>
      </section>
      <section className="field-teacher" id="features"><div className="field-width field-teacher-inner"><div><h2>{c('One topic.')}<br/><em>{c('A whole lesson.')}</em></h2><p>{c('Create your private prep library with lesson plans, quizzes, tests, flashcards, and activities.')}</p><Link href="/teacher" className="field-button field-button-light">{c('Explore teacher prep')}<StudioIcon name="arrow"/></Link></div><div className="field-teacher-materials"><p>{c('Your lesson, all together.')}</p>{['Lesson plan', 'Quiz', 'Flashcards', 'Presentation'].map((text, index) => <div key={text}><StudioIcon name={(['book', 'question', 'cards', 'presentation'] as const)[index]}/><span>{c(text)}</span><StudioIcon name="check"/></div>)}<small>{c('Teacher mode is self-selected. Your saved lessons are private.')}</small></div></div></section>
      <section className="field-questions field-width"><h2>{c('A few good questions.')}</h2><div>{[
        ['Can I use my own material?', 'Yes, in teacher mode. Upload a PDF, Word, or text file up to 10 MB, or paste text. Scanned PDFs need a text version for now.'],
        ['Which languages can I use?', 'Read and create in English, Russian, or Kazakh. Choose your interface and material languages separately.'],
        ['Can I edit what Fibonacci makes?', 'Yes. Explanations, quizzes, flashcards, and lesson materials can all be edited before you save or print them.'],
        ['What happens after the draft?', 'Review your story first. Video generation starts only when you choose to make it.'],
      ].map(([title, description]) => <details key={title}><summary>{c(title)}<StudioIcon name="plus"/></summary><p>{c(description)}</p></details>)}</div></section>
      <section className="field-last field-width"><Image className="field-last-art" src="/illustrations/hero-path.png" alt="" width={360} height={240}/><h2>{c('Your path starts')}<br/><em>{c('with one question.')}</em></h2><Link href={startHref} className="field-button">{c('Start learning')}<StudioIcon name="arrow"/></Link></section>
    </main>
    <footer className="field-footer field-width"><Link className="field-brand" href="/"><FibonacciMark size={26}/><span>fibonacci</span></Link><p>{c('Each step builds on the last.')}</p><nav aria-label={c('Explore Fibonacci')}><Link href="/teacher">{c('Teacher prep')}</Link><Link href="/login">{c('Sign in')}</Link><a href="#main-content">{c('Back to top')}</a></nav><small>© {new Date().getFullYear()} Fibonacci</small></footer>
  </div>
}
