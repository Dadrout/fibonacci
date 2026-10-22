'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from 'react'
import { FibonacciLogo } from '@/components/fibonacci-mark'
import { LanguagePicker } from '@/components/language-picker'
import { ThemeToggle } from '@/components/theme-toggle'
import { useCopy } from '@/hooks/use-copy'
import './landing.css'

const BOT = 'https://t.me/eduhack2026_bot'
const sampleItems = ['Blurry slide photo', 'YouTube lecture link', 'Lecture PDF']
const stages = ['Send sample', 'Reading', 'Filing', 'Linking', 'Filed']

function BrainLink({ className = '' }: { className?: string }) {
  const c = useCopy()
  return <Link className={`fl-primary ${className}`} href="/brain">{c('Open your Brain')}<span aria-hidden="true">↗</span></Link>
}

function SplitHero() {
  const c = useCopy()
  const [split, setSplit] = useState(50)
  const [mobile, setMobile] = useState(false)
  const frame = useRef<HTMLElement>(null)
  useEffect(() => {
    const query = window.matchMedia('(max-width: 760px)')
    const sync = () => { setMobile(query.matches); setSplit(value => Math.max(query.matches ? 42 : 38, Math.min(query.matches ? 56 : 62, value))) }
    sync(); query.addEventListener('change', sync)
    return () => query.removeEventListener('change', sync)
  }, [])
  const min = mobile ? 42 : 38
  const max = mobile ? 56 : 62
  const move = (event: PointerEvent<HTMLDivElement>) => {
    const rect = frame.current?.getBoundingClientRect()
    if (!rect) return
    const value = mobile ? (event.clientY - rect.top) / rect.height : (event.clientX - rect.left) / rect.width
    setSplit(Math.max(min, Math.min(max, Math.round(value * 100))))
  }
  return <section className="fl-hero" ref={frame} style={{ '--split': `${split}%` } as CSSProperties} aria-label={c('From your camera roll to your Brain')}>
    <div className="fl-mess-ground" />
    <h1><span>{c('Stop organizing.')}</span><span>{c('Start learning.')}</span></h1>
    <p className="fl-hero-sub"><span>{c('Photos, links and PDFs everywhere —')}</span><span>{c('Fibonacci files them for you.')}</span></p>
    <div className="fl-mess" aria-label={c('Your scattered study materials')}>
      <div className="fl-photo fl-photo-one"><span>{c('IMG_4471.jpg · blurry slide')}</span><div className="fl-chalk">Var(ε | X) ≠ σ²</div><i /><i /><i /></div>
      <div className="fl-photo fl-photo-two"><span>{c('IMG_4480.jpg · whiteboard')}</span><div className="fl-chalk">y = β₀ + β₁x + ε</div><i /><i /></div>
      <div className="fl-file fl-pdf">{c('ECON301_Week6 (2).pdf')}</div>
      <div className="fl-file fl-tabs">{c('47 open tabs')}<span aria-hidden="true">▱ ▱ ▱</span></div>
      <div className="fl-photo fl-photo-three"><span>{c('Screenshot · Oct 3')}</span><div className="fl-chalk">∑ (yᵢ − ŷᵢ)²</div><i /><i /></div>
      <div className="fl-file fl-voice"><span aria-hidden="true">▏▎▌▊▍▏▌▎▊▍</span>{c('Voice note · 0:48')}</div>
    </div>
    <div className="fl-course-columns" aria-label={c('Sample courses')}>
      {[
        ['Econometrics', 'Week 6 · Heteroskedasticity', '3 sources', 'Week 8 · Autocorrelation'],
        ['Probability & Statistics', 'Variance', '4 sources', 'Law of large numbers'],
        ['Calculus II', 'Taylor series', '3 sources', 'Improper integrals'],
      ].map(([name, topic, count, other], index) => <section className={`fl-course fl-course-${index}`} key={name}>
        <h2>{c(name)}</h2><div className="fl-course-item">{c(topic)}<small>{c(count)}</small></div><div className="fl-course-item">{c(other)}</div>
        {index === 0 && <p className="fl-gold">{c('Week 7 is missing')}</p>}
      </section>)}
    </div>
    <div className="fl-divider" aria-hidden="true" />
    <div className="fl-handle-cluster">
      <div className="fl-slider" role="slider" tabIndex={0} aria-label={c('Reveal the mess or the Brain')} aria-describedby="fl-slider-help" aria-valuemin={min} aria-valuemax={max} aria-valuenow={split} aria-orientation={mobile ? 'vertical' : 'horizontal'}
        onPointerDown={event => { event.currentTarget.setPointerCapture(event.pointerId); move(event) }}
        onPointerMove={event => { if (event.currentTarget.hasPointerCapture(event.pointerId)) move(event) }}
        onPointerUp={event => { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId) }}
        onKeyDown={event => {
          const direction = ['ArrowRight', 'ArrowDown'].includes(event.key) ? 2 : ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -2 : 0
          if (direction || event.key === 'Home' || event.key === 'End') { event.preventDefault(); setSplit(value => event.key === 'Home' ? min : event.key === 'End' ? max : Math.max(min, Math.min(max, value + direction))) }
        }}><span aria-hidden="true">{mobile ? '↕' : '↔'}</span></div>
      <BrainLink />
      <div className="fl-split-buttons"><button type="button" aria-label={c('Reveal more Brain')} onClick={() => setSplit(value => Math.max(min, value - 4))}>−</button><button type="button" aria-label={c('Reveal more mess')} onClick={() => setSplit(value => Math.min(max, value + 4))}>+</button></div>
    </div>
    <span id="fl-slider-help" className="sr-only">{c('Drag the divider or use the arrow keys. The buttons also adjust the split.')}</span>
    <div className="fl-flight" aria-hidden="true">{sampleItems.map((item, i) => <span key={item} style={{ '--flight-delay': `${450 + i * 260}ms`, '--flight-y': `${330 + i * 38}px` } as CSSProperties}>{c(item)}</span>)}</div>
    <p className="fl-hero-label fl-before">{c('Your camera roll, today')}</p><p className="fl-hero-label fl-after">{c('Your Brain, with everything in its place')}</p>
  </section>
}

function BrowserSample() {
  const c = useCopy()
  const [state, setState] = useState([0, 0, 0])
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])
  useEffect(() => () => timers.current.forEach(clearTimeout), [])
  function send(index: number) {
    setState(previous => previous.map((value, i) => i === index ? 1 : value))
    for (let step = 2; step <= 4; step++) {
      timers.current.push(setTimeout(() => setState(previous => previous.map((value, i) => i === index ? step : value)), (step - 1) * 650))
    }
  }
  function reset() { timers.current.forEach(clearTimeout); timers.current = []; setState([0, 0, 0]) }
  return <section className="fl-sample fl-wrap" aria-labelledby="fl-try-title">
    <div className="fl-section-intro"><div><h2 id="fl-try-title">{c('Give the mess somewhere to go.')}</h2><p>{c('Sample — runs in your browser')}</p></div><button className="fl-text-button" type="button" onClick={reset}>{c('Reset sample')}<span aria-hidden="true">↺</span></button></div>
    <div className="fl-sample-grid"><div><p>{c('Send these three sample sources.')}</p><div className="fl-send-list">{sampleItems.map((item, index) => <button key={item} type="button" disabled={state[index] !== 0} onClick={() => send(index)}><span><span className="fl-sample-kind" aria-hidden="true">{c(['JPG', 'URL', 'PDF'][index])}</span>{c(item)}</span><span>{c(stages[state[index]])}<span aria-hidden="true"> {state[index] === 4 ? '✓' : '→'}</span></span></button>)}</div></div>
    <div className="fl-sample-destination"><h3>{c('Econometrics')} <span aria-hidden="true">→</span> {c('Heteroskedasticity')}</h3><div className="fl-sample-results" aria-live="polite" aria-atomic="true">{state.every(value => value === 0) ? <p className="fl-muted">{c('Your sources will land here.')}</p> : sampleItems.map((item, index) => state[index] > 0 && <p key={item} className={state[index] === 4 ? 'fl-landed' : ''}><span>{c(item)}</span><span>{c(stages[state[index]])}{state[index] === 4 && ' ✓'}</span></p>)}</div></div></div>
    <div className="fl-connection" role="status">{state.every(value => value === 4) ? <p>{c('New connection: Heteroskedasticity ↔ Variance (Probability & Statistics)')}</p> : <p className="fl-muted">{c('Send all three to see a connection across courses.')}</p>}</div>
  </section>
}

function TelegramSection() {
  const c = useCopy()
  const [qr, setQr] = useState('')
  useEffect(() => {
    let active = true
    import('qrcode').then(module => module.toDataURL(BOT, { width: 240, margin: 4, errorCorrectionLevel: 'M' })).then(url => { if (active) setQr(url) }).catch(() => {})
    return () => { active = false }
  }, [])
  return <section id="telegram" className="fl-telegram fl-wrap" aria-labelledby="fl-telegram-title"><div><h2 id="fl-telegram-title">{c('Already in Telegram? Stay there.')}</h2><p>{c('A lecture photo between messages. A PDF from your class chat. Forward it, then get back to your day.')}</p><ol>{['Open the bot', 'Connect from Fibonacci', 'Forward anything'].map(item => <li key={item}>{c(item)}</li>)}</ol><a className="fl-bot-link" href={BOT}>{c('@eduhack2026_bot')} <span aria-hidden="true">↗</span></a></div><a className="fl-qr" href={BOT}>{qr ? <img src={qr} width={240} height={240} alt={c('QR code that opens the Fibonacci bot in Telegram')} /> : <span className="fl-qr-placeholder">{c('Open the bot')} ↗</span>}<span>{c('Scan to open Telegram')}</span></a></section>
}

const stories = [
  { title: 'Drop anything.', text: 'A photo, a link, a PDF or a voice note. Drop it into Fibonacci, paste it, or forward it to the Telegram bot.', image: 'brain-home.png', alt: 'The real Fibonacci home with three newly filed sources and the New connections panel', caption: 'Your material, arriving and finding its course.' },
  { title: 'It files itself.', text: 'Course → topic, without a folder picker. See the confidence of each match and correct it when needed.', image: 'brain-home.png', alt: 'Fibonacci source rows showing their assigned course and topic with confidence', caption: 'A course and topic for each source. Confidence stays visible.' },
  { title: 'Your courses start talking.', text: 'Heteroskedasticity in Econometrics meets variance in Probability & Statistics. Follow the connection on your Brain map.', image: 'brain-map.png', alt: 'The real Fibonacci Brain map connecting concepts across courses', caption: 'One map, with connections across your courses.' },
  { title: 'Exam in 3 days. A place to start.', text: 'Get a day-by-day plan and a quiz from your own material. Answer wrong, and open the exact slide, page or video moment that explains it.', image: 'exam-plan.png', alt: 'A real three-day Fibonacci exam plan with source citations beside study tasks', caption: 'A plan for each day, with your sources beside every task.' },
]

export function FibonacciLanding() {
  const c = useCopy()
  return <div className="fib-landing">
    <a className="fl-skip" href="#landing-main">{c('Skip to content')}</a>
    <header className="fl-header"><Link href="/" aria-label={c('Fibonacci home')}><FibonacciLogo size={32} /></Link><nav aria-label={c('Main navigation')}><a href="#how-it-works">{c('How it works')}</a><a href="#telegram">{c('Telegram')}</a><a href="#exams">{c('Exams')}</a></nav><div className="fl-header-tools"><LanguagePicker /><ThemeToggle /><BrainLink /></div></header>
    <main id="landing-main"><SplitHero />
      <section id="how-it-works" className="fl-how fl-wrap" aria-labelledby="fl-how-title"><h2 id="fl-how-title">{c('From scattered sources to understanding.')}</h2><p className="fl-how-lead">{c('Your material does the teaching. Fibonacci makes it easier to find, connect and learn.')}</p>
        {stories.map((story, index) => <article className={`fl-story ${index % 2 ? 'fl-story-reverse' : ''}`} id={index === 3 ? 'exams' : undefined} key={story.title}><div className="fl-story-copy"><span className="fl-step" aria-hidden="true">0{index + 1}</span><h3>{c(story.title)}</h3><p>{c(story.text)}</p>{index === 0 && <a href="#try-it">{c('Try the browser sample')} <span aria-hidden="true">↓</span></a>}</div><figure><Image src={`/landing/${story.image}`} width={story.image === 'brain-map.png' ? 2320 : 2560} height={story.image === 'brain-map.png' ? 1554 : 1600} sizes="(max-width: 760px) 100vw, 65vw" alt={c(story.alt)} /><figcaption>{c(story.caption)}</figcaption></figure></article>)}
        <figure className="fl-mistake"><Image src="/landing/mistake-moment.png" width={2560} height={1600} sizes="(max-width: 760px) 100vw, 80vw" alt={c('A wrong quiz answer in Fibonacci opening the original source moment with its explanation')} /><figcaption>{c('A wrong answer is a way back to the part you missed.')}</figcaption></figure>
      </section>
      <div id="try-it"><BrowserSample /></div><TelegramSection />
      <section className="fl-facts fl-wrap" aria-labelledby="fl-facts-title"><h2 id="fl-facts-title">{c('A few things you can count on.')}</h2><dl><div><dt>{c('Three sources filed in about 2 seconds')}</dt><dd>{c('Measured: 1.6 s on 22 Oct 2026.')}</dd></div><div><dt>{c('Every line of your exam plan cites your own slide, page or video moment')}</dt><dd>{c('Go straight to the source.')}</dd></div><div><dt>{c('English, Русский, Қазақша')}</dt><dd>{c('Learn in your language.')}</dd></div><div><dt>{c('Forward from Telegram — no folders')}</dt><dd>{c('Your material finds its course.')}</dd></div></dl></section>
      <section className="fl-closing"><h2>{c('Less sorting. More understanding.')}</h2><div><BrainLink /><a href={BOT} className="fl-secondary">{c('Message the bot')} <span aria-hidden="true">↗</span></a></div></section>
    </main><footer className="fl-footer fl-wrap"><FibonacciLogo size={26} /><p>{c('A second brain that builds itself.')}</p><a href="#landing-main">{c('Back to top')} ↑</a></footer>
  </div>
}
