---
name: Fibonacci
description: "Seedhead: a learning path where each idea is a seed placed at the golden angle."
colors:
  studio-paper: "#f6f7f5"
  studio-surface: "#ffffff"
  studio-ink: "#16191d"
  studio-muted: "#5a6170"
  studio-line: "#d9dde3"
  studio-green: "#2346d8"
  studio-green-hover: "#1b37b0"
  studio-on-green: "#ffffff"
  studio-accent: "#8f5e00"
  studio-gold: "#e0a526"
  studio-sage: "#e9edfb"
  studio-map-ink: "#2f3f8f"
  studio-dark-paper: "#0e1014"
  studio-dark-surface: "#161a21"
  studio-dark-ink: "#eceef2"
  studio-dark-muted: "#a5acb8"
  studio-dark-line: "#2c323d"
  studio-dark-green: "#8ea6ff"
  studio-dark-green-hover: "#a9bbff"
  studio-dark-on-green: "#0e1014"
  studio-dark-accent: "#f0bf5a"
  studio-dark-sage: "#1b2133"
  studio-dark-map-ink: "#b7c5ff"
typography:
  display:
    fontFamily: "Literata, Georgia, serif"
    fontSize: "clamp(46px, 5vw, 76px)"
    fontWeight: 450
    lineHeight: 1.12
    letterSpacing: "-0.04em"
  title:
    fontFamily: "Literata, Georgia, serif"
    fontSize: "27px"
    fontWeight: 450
    lineHeight: 1.35
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Golos Text, Noto Sans, sans-serif"
    fontSize: "15px"
    lineHeight: 1.75
  label:
    fontFamily: "Golos Text, Noto Sans, sans-serif"
    fontSize: "14px"
    fontWeight: 600
rounded:
  control: "6px"
  working-surface: "10px"
  account-surface: "12px"
spacing:
  space-4: "4px"
  space-8: "8px"
  space-12: "12px"
  space-16: "16px"
  space-24: "24px"
  space-32: "32px"
  space-48: "48px"
  space-64: "64px"
components:
  button-primary:
    backgroundColor: "{colors.studio-green}"
    textColor: "{colors.studio-on-green}"
    rounded: "{rounded.control}"
    padding: "14px 22px"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.studio-green-hover}"
  button-light:
    backgroundColor: "{colors.studio-on-green}"
    textColor: "{colors.studio-green}"
    rounded: "{rounded.control}"
    padding: "14px 22px"
  input-topic:
    textColor: "{colors.studio-ink}"
    rounded: "5px"
    padding: "0 11px"
  navigation:
    textColor: "{colors.studio-ink}"
  story-card:
    backgroundColor: "{colors.studio-surface}"
    textColor: "{colors.studio-ink}"
    rounded: "{rounded.working-surface}"
  material-choice:
    backgroundColor: "{colors.studio-sage}"
    textColor: "{colors.studio-green}"
    rounded: "{rounded.control}"
    padding: "13px 11px"
---
# Fibonacci visual system

**Direction: Seedhead** (chosen 20 Oct 2026; see `docs/fibonacci-plan.html`). Each idea in a learning path is a seed placed at the golden angle (~137.5°), the arrangement a sunflower uses. Colours: ink and cobalt blue. Cobalt (`--studio-green`, name kept for compatibility) is for actions. Gold (`--studio-gold`) marks progress and source highlights only; `--studio-accent` is its darker, text-safe version. Gold is never a button colour. Use the seedhead sparingly. The old owl logo is retired.

**Logo (22 Oct 2026):** the Codex image-generated mark is a growing spiral of six broad cobalt seeds around one gold spark, suggesting ideas assembling into a second brain. Option 2 was chosen for its simple silhouette and small-size clarity. The original, two runner-ups, transparent 512/192px marks, dark-theme header variant, favicons, opaque Apple icon, and generation prompts live in `wizetale-app/public/brand/`; Next.js icons live at `wizetale-app/app/icon.png` and `app/apple-icon.png`. `FibonacciLogo` uses the new image beside the existing wordmark; the SVG `FibonacciMark` and its filled-seed progress behavior remain unchanged.

Fibonacci is a second brain for students that builds itself (see `PRODUCT.md`). The product surface is the Brain: one calm home with drill-down pages for a course, all sources, and an exam plan. It is an Operate surface — scanability, consistency, and the presenter's stage path come before expression; the brand lives in precise details.

## Visual direction

The interface borrows the clarity of an educational field guide: paper surfaces, cobalt actions, gold reserved for sources and progress, a readable serif for learning content, and practical sans-serif controls. Use the Fibonacci seedhead mark as the brand asset. Useful content and diagrams lead; omit stock photography, decoration-only illustration, moving tickers, and gradient ornament.

- Headings and narrative emphasis: locally hosted **Literata**, generally weight 450–500, line height 1.12–1.35, tracking no tighter than −0.04em.
- Body, navigation, controls: locally hosted **Golos Text**, weight 400–650, body line height 1.6–1.85.
- Both variable fonts include Russian and Kazakh characters, including Ә Ғ Қ Ң Ө Ұ Ү Һ І. Fonts and SIL OFL licenses live in `wizetale-app/public/fonts`.
- Marketing display: 39–76px, responsive and wrapping naturally. Product headings: 30–56px. Primary working text: 14–16px.

## Semantic tokens

`wizetale-app/app/globals.css` owns the source of truth. Existing `--ts-*`, `--workspace-*`, and Tailwind semantic tokens map onto the new palette, preserving consumers.

| Token | Light | Dark | Role |
| --- | --- | --- | --- |
| `--studio-paper` | `#f6f7f5` | `#0e1014` | Page |
| `--studio-surface` | `#ffffff` | `#161a21` | Working surface |
| `--studio-ink` | `#16191d` | `#eceef2` | Text |
| `--studio-muted` | `#5a6170` | `#a5acb8` | Supporting text |
| `--studio-line` | `#d9dde3` | `#2c323d` | Dividers |
| `--studio-green` | `#2346d8` | `#8ea6ff` | Primary action (cobalt; name kept for compatibility) |
| `--studio-on-green` | `#ffffff` | `#0e1014` | Action foreground |
| `--studio-accent` | `#8f5e00` | `#f0bf5a` | Text-safe gold: citations, focus, review states |
| `--studio-gold` | `#e0a526` | `#f0bf5a` | Source and progress highlights (never a button) |
| `--studio-sage` | `#e9edfb` | `#1b2133` | Context surfaces (pale cobalt) |

Measured contrast (22 Oct 2026, WCAG 2.1): light text 16.4:1 on paper; supporting text 5.8:1 on paper, 6.2:1 on surface, 5.3:1 on sage; action pair 7.2:1; accent text 5.6:1. Dark text 16.4:1; supporting text 8.3:1 on paper, 7.6:1 on surface; action pair 8.2:1; accent text 10.2:1. All pairs pass AA.

## Components and layout

- Spacing rhythm: 4, 8, 12, 16, 24, 32, 48, 64px. Brain content maximum width 1160px. Gutters shrink from 56px to 32px to 14–16px.
- Working surfaces use a single quiet border and 10–12px radius. Controls use 5–6px radii. Avoid nested decorative cards.
- Buttons and important controls have a minimum 44px interaction target; generation actions generally 52px. Use visible 3px focus outlines and native disabled semantics.
- **Brain patterns (polish pass, 22 Oct 2026):**
  - *Filed source* is one row: preview, title with kind and date, then "course → topic" in the course colour, confidence, and *Not right?* on the right. On the course page the path is hidden (the page already groups by topic). *Not right?* offers suggestions and always a *Move to* course/topic picker.
  - *New connections* arrive as one panel with a count, one row per link, *See on the map*, and a single dismiss — never one banner per link.
  - *Citation chips* are compact gold-tinted tags (30px, 44px on touch and in presentation mode); plans show three per task and "+N more".
  - Course colour appears as a swatch dot, a tint, or text colour — never as a thick side or top stripe. Colored `border-left`/`border-top` over 1px on cards, callouts or list items is not used.
  - No small uppercase label above a heading: context goes in a meta line under the title (e.g. "Econometrics · Exam on Sun, Oct 25 · 3 days").
  - Back links sit at the left above the page title; the page's main action sits on the title row.
  - One surface per piece of content: no cards inside cards.
- SVG control artwork is authored in `components/studio-icon.tsx`; existing leaf controls may retain their existing icons. Text labels carry meaning. Do not introduce emoji as controls.
- Theme controls use `next-themes`, with hydration-safe state and localized accessible labels. Locale switching must not change the heading family.

## Interaction and accessibility

Keep native buttons, selects, details/summary, and explicit labels. Selection uses `aria-pressed` or `aria-current`, and state is indicated with more than color. Auth failures retain inline errors and focus a linked summary. Password controls announce their action and state; autocomplete supports password managers.

Motion is short color feedback, approximately 180ms, plus one authored moment: a source landing in its course (the path slides in with a fading course tint) and new connections lighting up on the map. Everything respects the user's reduced-motion setting.

## Validation boundaries

Use existing backend contracts and authenticated API calls. The local preview flag remains opt-in and serves sample content only. Never bypass authentication or fabricate data for demonstrations: demo tools send the real demo files through the real pipeline (D18). Verify every change on the hero demo path (`docs/brain/DEMO_SCRIPT.md`) at 1366px, 390px and 320px, light and dark, en/ru/kk.
