---
name: Fibonacci
description: "An editorial learning studio inspired by an educational field guide."
colors:
  studio-paper: "#f7f5ee"
  studio-surface: "#fffef9"
  studio-ink: "#252d29"
  studio-muted: "#626a61"
  studio-line: "#d6dbcf"
  studio-green: "#234d3d"
  studio-green-hover: "#183d2e"
  studio-on-green: "#fffef5"
  studio-accent: "#ad4a32"
  studio-sage: "#e5eadc"
  studio-map-ink: "#435d43"
  studio-dark-paper: "#18231e"
  studio-dark-surface: "#202e26"
  studio-dark-ink: "#f1f1e4"
  studio-dark-muted: "#b6c1b4"
  studio-dark-line: "#425447"
  studio-dark-green: "#b9d3a5"
  studio-dark-green-hover: "#c9e1b7"
  studio-dark-on-green: "#1a2b20"
  studio-dark-accent: "#eea184"
  studio-dark-sage: "#2c3f30"
  studio-dark-map-ink: "#c0d4b1"
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

Fibonacci is an editorial learning studio for curious learners aged 10–18 and teachers preparing private lesson materials. Product behavior, authentication, content ownership, generation, and source review remain in the existing Next.js and API architecture.

## Visual direction

The interface borrows the clarity of an educational field guide: paper surfaces, deep green actions, a restrained vermilion accent, a readable serif for learning content, and practical sans-serif controls. Keep the supplied Fibonacci owl as the brand asset. Useful content and diagrams lead; omit stock photography, decoration-only illustration, moving tickers, and gradient ornament.

- Headings and narrative emphasis: locally hosted **Literata**, generally weight 450–500, line height 1.12–1.35, tracking no tighter than −0.04em.
- Body, navigation, controls: locally hosted **Golos Text**, weight 400–650, body line height 1.6–1.85.
- Both variable fonts include Russian and Kazakh characters, including Ә Ғ Қ Ң Ө Ұ Ү Һ І. Fonts and SIL OFL licenses live in `wizetale-app/public/fonts`.
- Marketing display: 39–76px, responsive and wrapping naturally. Product headings: 30–56px. Primary working text: 14–16px.

## Semantic tokens

`wizetale-app/app/globals.css` owns the source of truth. Existing `--ts-*`, `--workspace-*`, and Tailwind semantic tokens map onto the new palette, preserving consumers.

| Token | Light | Dark | Role |
| --- | --- | --- | --- |
| `--studio-paper` | `#f7f5ee` | `#18231e` | Page |
| `--studio-surface` | `#fffef9` | `#202e26` | Working surface |
| `--studio-ink` | `#252d29` | `#f1f1e4` | Text |
| `--studio-muted` | `#626a61` | `#b6c1b4` | Supporting text |
| `--studio-line` | `#d6dbcf` | `#425447` | Dividers |
| `--studio-green` | `#234d3d` | `#b9d3a5` | Primary action |
| `--studio-on-green` | `#fffef5` | `#1a2b20` | Action foreground |
| `--studio-accent` | `#ad4a32` | `#eea184` | Focus and occasional emphasis |
| `--studio-sage` | `#e5eadc` | `#2c3f30` | Context surfaces |

Core measured contrast: light primary text 12.95:1; light supporting text 5.13:1 on paper and 4.56:1 on sage; action pair 9.43:1. Dark primary text 14.21:1; supporting text 7.62:1 on the working surface; action pair 9.16:1.

## Components and layout

- Spacing rhythm: 4, 8, 12, 16, 24, 32, 48, 64px. Marketing maximum width 1280px; teacher content 1160px. Gutters shrink from 56px to 32px to 16–20px.
- Working surfaces use a single quiet border and 10–12px radius. Controls use 5–6px radii. Avoid nested decorative cards.
- Buttons and important controls have a minimum 44px interaction target; generation actions generally 52px. Use visible 3px focus outlines and native disabled semantics.
- The landing uses a two-column editorial introduction and a live sample. The SVG is a labeled schematic of a route, not a geographic map. The quiz is a local example, explicitly labeled as sample content.
- The learner studio places shared topic setup beside the active editor. At 800px and below, it becomes one column; small-phone subject/language fields share a row. Optional question suggestions use native disclosure.
- Teacher lessons, sources, resource editing, study tools, presentations, and account screens inherit the shared tokens. Preserve their data flow and print behavior.
- SVG control artwork is authored in `components/studio-icon.tsx`; existing leaf controls may retain their existing icons. Text labels carry meaning. Do not introduce emoji as controls.
- Theme controls use `next-themes`, with hydration-safe state and localized accessible labels. Locale switching must not change the heading family.

## Interaction and accessibility

Keep native buttons, selects, details/summary, and explicit labels. Selection uses `aria-pressed` or `aria-current`, and state is indicated with more than color. Auth failures retain inline errors and focus a linked summary. Password controls announce their action and state; autocomplete supports password managers.

Motion is short color feedback, approximately 180ms, and the existing draft transition respects the user's reduced-motion setting. No automatic ticker or continuous decorative animation is shipped on the landing. Maintain the existing reduced-motion overrides in student and teacher flows.

## Validation boundaries

Use existing backend contracts and authenticated API calls. The local preview flag remains opt-in and serves sample content only. Never bypass authentication or fabricate saved lessons for visual demonstrations. Verify authenticated generation and printing in a connected test environment before release.
