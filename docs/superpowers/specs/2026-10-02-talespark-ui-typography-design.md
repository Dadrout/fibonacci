# TaleSpark UI and Typography Refresh

## Purpose

Create a consistent, readable visual system for TaleSpark, an educational storytelling app for learners aged 10–18. The refresh should make the experience feel warm and imaginative while keeping story creation, reading, and account tasks clear and comfortable on desktop and mobile.

## Current context

- The home page has its own bold storybook identity, using the local TaleSpark Display font and Inter.
- The story creation workspace has a separate pastel dashboard style and loads Inter independently.
- Sign-in and account-related screens inherit generic app styling and may fall back to Arial.
- History and generated-story screens use another set of utility-class styles and do not share the dashboard typography or surface treatment.
- The app already includes light and dark theme support; the refresh must keep both usable.

## Chosen direction

Keep the distinctive TaleSpark landing-page personality, then carry a calmer storybook look across the app. Use warm paper-like backgrounds, deep readable ink, and a restrained violet/sky palette, with yellow and mint used for small moments of emphasis. Cards may use soft color fills and friendly rounded corners, but avoid relying on heavy 3D effects or shadows to communicate hierarchy.

### Typography

- Use Fredoka for headings and Nunito for interface and reading text.
- Keep the existing TaleSpark Display font for the brand wordmark or a small number of oversized brand moments only.
- Bundle font files with the app using the fonts’ open licenses; do not load fonts from a third-party runtime service.
- Define one shared font setup at the app root so all routes render consistently. Remove per-page duplicate font setup where it is no longer needed.
- Establish a responsive type scale with comfortable body copy (16px minimum for primary reading text), clear heading levels, readable line spacing, and limited line lengths for longer narration and recaps.

### Shared UI language

- Align page backgrounds, text colors, borders, corner radii, and spacing across routes through shared design tokens.
- Make links, primary and secondary actions, form controls, cards, loading states, errors, and empty states feel like parts of the same product.
- Keep interactive targets comfortably large, provide visible keyboard focus, maintain strong text contrast, and respect reduced-motion preferences.
- Preserve the meaning and behavior of existing controls and keep the current light and dark themes supported.

## Coverage

Apply the system to these five areas:

1. Public landing page.
2. Story creation workspace.
3. Sign-in and registration screens.
4. Story history and generated-story detail.
5. Profile and account screens.

This is a visual and typographic refresh only. Do not change story generation, authentication, account deletion, API behavior, or content flow.

## Acceptance criteria

- All covered areas use the same bundled heading and body font families, with the brand display font reserved for branding.
- Page backgrounds, text hierarchy, form controls, buttons, links, cards, and feedback states look coherent across the covered routes.
- Body and reading text remain legible at mobile widths without clipping or horizontal scrolling.
- Light and dark themes remain readable, and keyboard focus, contrast, and reduced-motion support are preserved.
- The existing application build completes successfully after the visual changes.

## Risks and constraints

- Fredoka must remain limited to headings so longer educational text stays easy to read.
- Local font files increase the static asset footprint; use only required weights/subsets and preserve their license files.
- Some current screens use route-specific CSS and some use utility classes; centralize only shared visual foundations and keep route-specific layouts intact.
- No repository behavior or data contract should change as part of this work.
