'use client'

import { useCopy } from '@/hooks/use-copy'

import Image from 'next/image'
import Link from 'next/link'
import { useState } from 'react'
import { LanguagePicker } from '@/components/language-picker'

const steps = [
  {
    number: '01',
    label: 'START WITH A QUESTION',
    mark: '✳',
    color: 'slush-yellow',
    title: 'Choose a question',
    description: 'Pick a subject and bring the thing you have been wondering about.',
  },
  {
    number: '02',
    label: 'MAKE IT YOURS',
    mark: '✦',
    color: 'slush-lavender',
    title: 'Shape the story',
    description: 'Get an age-aware first draft you can read through and edit.',
  },
  {
    number: '03',
    label: 'KEEP THE GOOD PARTS',
    mark: '↗',
    color: 'slush-mint',
    title: 'Remember what matters',
    description: 'Use a short recap and quiz to make the big ideas stick.',
  },
]

const features = [
  { mark: 'Aa', title: 'A script before a screen', description: 'See the words first. Make changes before you decide what comes next.' },
  { mark: '↗', title: 'Made for your age', description: 'Stories are shaped around the learner, so new ideas feel within reach.' },
  { mark: '✳', title: 'Room for curiosity', description: 'Explore history, geography, and the questions that connect them.' },
]

function RibbonArt() {
  const c = useCopy()

  return (
    <div className="slush-art" aria-hidden="true">
      <svg className="slush-ribbon" viewBox="0 0 900 620" fill="none" role="presentation">
        <path d="M47 407C164 115 293 110 374 312S528 510 606 279 750 76 858 198" stroke="#000" strokeWidth="104" strokeLinecap="round" />
        <path d="M47 407C164 115 293 110 374 312S528 510 606 279 750 76 858 198" stroke="#4da2ff" strokeWidth="96" strokeLinecap="round" />
        <path d="M77 383C183 167 293 163 362 328" stroke="#9bceff" strokeWidth="20" strokeLinecap="round" opacity=".72" />
      </svg>
      <span className="slush-sticker slush-sticker-star">✦</span>
      <span className="slush-sticker slush-sticker-sun">✳</span>
      <span className="slush-sticker slush-sticker-heart">♥</span>
      <span className="slush-art-label"> {c("A QUESTION")} <br /> {c("CAN GO PLACES")} </span>
    </div>
  )
}

export default function SlushLanding({ previewEnabled }: { previewEnabled: boolean }) {
  const c = useCopy()

  const [menuOpen, setMenuOpen] = useState(false)
  const startHref = previewEnabled ? '/create?preview=1' : '/register'

  const closeMenu = () => setMenuOpen(false)

  return (
    <main className="slush-page">
      <div className="slush-topline" aria-label={c("Stories begin with good questions")}> {c("GOOD QUESTIONS GO PLACES")} <span aria-hidden="true">✦</span> {c("GOOD QUESTIONS GO PLACES")} <span aria-hidden="true">✦</span> {c("GOOD QUESTIONS GO PLACES")} </div>

      <header className="slush-header">
        <div className="slush-container slush-header-inner">
          <Link href="/" className="slush-brand" aria-label={c("TaleSpark home")}>
            <Image src="/talespark-logo-owl.png" alt="TaleSpark" width={74} height={74} priority />
          </Link>

          <nav className="slush-nav" aria-label={c("Main navigation")}>
            <a href="#how-it-works"> {c("How it works")} </a>
            <a href="#story-preview"> {c("Story preview")} </a>
            <a href="#features"> {c("Why TaleSpark")} </a>
            <Link href="/teacher"> {c("Teacher prep")} </Link>
          </nav>

          <div className="slush-nav-actions">
            <Link href="/login" className="slush-text-link"> {c("Sign in")} </Link>
            <Link href={startHref} className="slush-button slush-button-black"> {c("Start learning")} <span aria-hidden="true">↗</span></Link>
          </div>

          <LanguagePicker className="slush-language-picker" />

          <button
            type="button"
            className="slush-menu-button"
            aria-label={menuOpen ? c("Close menu") : c("Open menu")}
            aria-expanded={menuOpen}
            aria-controls="slush-mobile-navigation"
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? '×' : '+'}
          </button>
        </div>

        {menuOpen && (
          <nav id="slush-mobile-navigation" className="slush-mobile-nav" aria-label={c("Mobile navigation")}>
            <a href="#how-it-works" onClick={closeMenu}> {c("How it works")} <span aria-hidden="true">↘</span></a>
            <a href="#story-preview" onClick={closeMenu}> {c("Story preview")} <span aria-hidden="true">↘</span></a>
            <a href="#features" onClick={closeMenu}> {c("Why TaleSpark")} <span aria-hidden="true">↘</span></a>
            <div>
              <Link href="/login" onClick={closeMenu}> {c("Sign in")} </Link>
              <Link href={startHref} className="slush-button slush-button-black" onClick={closeMenu}> {c("Start learning")} <span aria-hidden="true">↗</span></Link>
            </div>
          </nav>
        )}
      </header>

      <section className="slush-hero" id="top">
        <div className="slush-container slush-hero-inner">
          <div className="slush-hero-top">
            <span className="slush-kicker"><span aria-hidden="true" /> {c("MADE FOR CURIOUS MINDS")} </span>
            <span> {c("AGES 10–18 · ONE GOOD QUESTION AT A TIME")} </span>
          </div>

          <RibbonArt />

          <div className="slush-hero-copy">
            <h1><span> {c("Stories from")} </span><strong> {c("curiosity.")} </strong></h1>
            <div className="slush-hero-bottom">
              <p> {c("Turn a big question into a little story worth remembering.")} </p>
              <div className="slush-hero-actions">
                <Link href={startHref} className="slush-button slush-button-black"> {c("Make a story")} <span aria-hidden="true">↗</span></Link>
                <a href="#how-it-works" className="slush-text-link"><span aria-hidden="true">↓</span> {c("See how it works")} </a>
              </div>
            </div>
          </div>

          <div className="slush-hero-footer">
            <span> {c("HISTORY · GEOGRAPHY · BIG IDEAS")} </span>
            <span aria-hidden="true"> {c("SCROLL TO SPARK SOMETHING ↓")} </span>
          </div>
        </div>
      </section>

      <div className="slush-ticker" aria-hidden="true">
        <div> {c("MAKE ROOM FOR WONDER")} <span>✦</span> {c("ASK A BIG QUESTION")} <span>✦</span> {c("MAKE ROOM FOR WONDER")} <span>✦</span> {c("ASK A BIG QUESTION")} <span>✦</span></div>
      </div>

      <section className="slush-section slush-how" id="how-it-works">
        <div className="slush-container">
          <div className="slush-section-heading">
            <div>
              <span className="slush-eyebrow"> {c("A LITTLE ADVENTURE IN THREE STEPS")} </span>
              <h2> {c("From “why?”")} <br /> {c("to “I get it.”")} </h2>
            </div>
            <p> {c("Learning can start anywhere: a question from class, a place on a map, or a thought that will not leave you alone.")} </p>
          </div>

          <div className="slush-steps">
            {steps.map((step) => (
              <article className={`slush-step ${step.color}`} key={step.number}>
                <div className="slush-step-top"><span>{c(step.label)}</span><span>{step.number}</span></div>
                <div className="slush-step-graphic" aria-hidden="true">{step.mark}</div>
                <div className="slush-step-copy">
                  <h3>{c(step.title)}</h3>
                  <p>{c(step.description)}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="slush-demo" id="story-preview">
        <div className="slush-container slush-demo-inner">
          <div className="slush-demo-copy">
            <span className="slush-eyebrow"> {c("A SCRIPT YOU CAN MAKE YOURS")} </span>
            <h2> {c("Read it.")} <br /> {c("Edit it.")} <br /> {c("Own it.")} </h2>
            <p> {c("Every story starts with words you can see and change before you decide what to do next.")} </p>
            <span className="slush-demo-spark" aria-hidden="true">✳</span>
          </div>
          <article className="slush-script-preview" aria-label={c("Example story script")}>
            <div className="slush-script-top"><span><i aria-hidden="true" /> {c("SAMPLE SCRIPT")} </span><span>01 / 03</span></div>
            <p className="slush-script-question"> {c("What connected people along the Silk Road?")} </p>
            <div className="slush-script-rule" />
            <p> {c("Picture a long road with no single starting point. Traders carried silk, spices, and stories between towns. Along the way, ideas traveled too — changing the people who shared them.")} </p>
            <div className="slush-script-footer"><span> {c("✦ A STORY ABOUT CONNECTION")} </span><span> {c("EDITABLE DRAFT")} </span></div>
          </article>
        </div>
      </section>

      <section className="slush-features slush-section" id="features">
        <div className="slush-container">
          <div className="slush-section-heading">
            <div>
              <span className="slush-eyebrow"> {c("BUILT AROUND THE LEARNER")} </span>
              <h2> {c("Curiosity gets")} <br /> {c("the good stuff.")} </h2>
            </div>
            <p> {c("Big ideas, made easier to approach — with the learner in control of the story.")} </p>
          </div>
          <div className="slush-features-grid">
            {features.map((feature, index) => (
              <article className="slush-feature" key={c(feature.title)}>
                <span className="slush-feature-marker" aria-hidden="true">{feature.mark}</span>
                <span className="slush-feature-number">0{index + 1}</span>
                <h3>{c(feature.title)}</h3>
                <p>{c(feature.description)}</p>
                <span className="slush-feature-arrow" aria-hidden="true">↗</span>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="slush-interlude" aria-label={c("One question can change how you see the world")}>
        <div className="slush-container">
          <span className="slush-interlude-star" aria-hidden="true">✳</span>
          <p> {c("One question.")} <br /><em> {c("A whole new world.")} </em></p>
          <span className="slush-interlude-badge"> {c("GOOD QUESTIONS")} <br /> {c("GO PLACES ✦")} </span>
        </div>
      </section>

      <section className="slush-cta" id="start">
        <div className="slush-container slush-cta-inner">
          <div>
            <span className="slush-eyebrow"> {c("YOUR NEXT LITTLE ADVENTURE")} </span>
            <h2> {c("What are")} <br /> {c("you curious about?")} </h2>
            <p> {c("Bring your question. We’ll help you turn it into a story you can understand, shape, and remember.")} </p>
            <Link href={startHref} className="slush-button slush-button-black"> {c("Start with a question")} <span aria-hidden="true">↗</span></Link>
          </div>
          <div className="slush-story-card">
            <span className="slush-story-card-sticker" aria-hidden="true">✦</span>
            <span className="slush-eyebrow"> {c("A QUESTION IS A GREAT BEGINNING")} </span>
            <p>“{c('How did the Silk Road connect people?')}”</p>
            <span className="slush-story-card-bottom"> {c("HISTORY · PEOPLE & IDEAS")} </span>
          </div>
        </div>
      </section>

      <footer className="slush-footer">
        <div className="slush-container">
          <div className="slush-footer-main">
            <div>
              <Link href="/" className="slush-brand" aria-label={c("TaleSpark home")}>
                <Image src="/talespark-logo-owl.png" alt="TaleSpark" width={74} height={74} />
              </Link>
              <p> {c("Good questions go places. Let’s see where yours takes you.")} </p>
            </div>
            <nav aria-label={c("Explore TaleSpark")}>
              <span> {c("EXPLORE")} </span>
              <a href="#how-it-works"> {c("How it works")} </a>
              <a href="#story-preview"> {c("Story preview")} </a>
              <a href="#features"> {c("Why TaleSpark")} </a>
            <Link href="/teacher"> {c("Teacher prep")} </Link>
            </nav>
            <div className="slush-footer-join">
              <span> {c("READY WHEN YOU ARE")} </span>
              <Link href="/login" className="slush-text-link"> {c("Sign in")} <span aria-hidden="true">↗</span></Link>
              <Link href={startHref} className="slush-button slush-button-black"> {c("Start learning")} <span aria-hidden="true">↗</span></Link>
            </div>
          </div>
          <div className="slush-footer-bottom"><span>© {new Date().getFullYear()} TaleSpark</span><a href="#top"> {c("BACK TO TOP ↑")} </a></div>
        </div>
      </footer>
    </main>
  )
}
