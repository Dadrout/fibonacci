# Fibonacci UI and Typography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved warm storybook visual system and Fredoka/Nunito typography across Fibonacci’s public, learning, authentication, and account routes.

**Architecture:** Load the two variable fonts once through `next/font/local` in the root app layout, then expose shared type and color tokens from the existing global stylesheet. Keep the landing page and creation workspace layouts intact while updating their visual rules, then bring authentication and account/story routes onto the same tokens.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Tailwind CSS 3, `next/font/local`, existing CSS and shadcn-style UI components.

**Spec:** `docs/superpowers/specs/2026-10-02-fibonacci-ui-typography-design.md`

## Global Constraints

- Keep the work visual and typographic; preserve authentication, story generation, account deletion, API behavior, and content flow.
- Use bundled local Fredoka and Nunito font files and retain their OFL license files; do not make runtime requests to a font service.
- Use Fredoka for headings and Nunito for interface and reading text; reserve Fibonacci Display for brand marks and a few oversized brand moments.
- Keep light and dark themes readable, maintain visible keyboard focus, respect reduced-motion preferences, and keep primary reading text at least 16px.
- Do not add product dependencies or refactor unrelated route behavior.
- The workspace has no usable Git repository, so implementation commits cannot be created here.

## Review Focus

- At narrow widths (320px and 375px), long headings and actions must wrap without clipping or horizontal page scroll; review `/`, `/create`, `/history`, and `/profile`.
- In both light and dark themes, body copy, form feedback, cards, and controls must remain legible; review `/login`, `/register`, `/reset-password`, `/reset-password/update`, `/verify-email`, `/history`, `/story/<taskId>`, and `/profile`.
- Keyboard users must be able to identify the focused link, input, button, select, and disclosure control; review the primary interactions on `/`, `/create`, `/login`, and `/profile`.
- Reduced-motion preference must suppress decorative landing and workspace animations without hiding content; review `/` and `/create`.
- The font files must load locally with the intended variable weights and a system fallback; inspect computed fonts and the network panel on `/` and `/login`.

---

### Task 1: Establish shared local fonts and design tokens

**Files:**
- Create: `wizetale-app/public/fonts/Fredoka-Variable.ttf`
- Create: `wizetale-app/public/fonts/Nunito-Variable.ttf`
- Create: `wizetale-app/public/fonts/Fredoka-OFL.txt`
- Create: `wizetale-app/public/fonts/Nunito-OFL.txt`
- Modify: `wizetale-app/app/layout.tsx`
- Modify: `wizetale-app/app/globals.css`
- Modify: `wizetale-app/app/page.tsx`
- Modify: `wizetale-app/app/create/page.tsx`

**Interfaces:**
- Consumes: existing `next/font/local` setup and app-wide light/dark theme classes.
- Produces: root CSS variables `--font-heading` and `--font-body`, shared paper/ink/accent/surface/border tokens, and a root body font assignment used by every route.

- [x] **Step 1: Add the variable font assets and license files**

Use the official Google Fonts repository’s full variable TrueType assets for Fredoka and Nunito, saving them under the names listed above. Preserve Latin and Cyrillic glyph coverage for the existing English and Russian UI. Preserve each family’s SIL Open Font License text alongside the assets.

- [x] **Step 2: Configure root font loading and shared tokens**

Load each local variable font once in `app/layout.tsx` with Fredoka weights 300–700 and Nunito weights 200–1000, expose `--font-heading` and `--font-body`, set the app body to Nunito, set global heading styles to Fredoka, and define the approved light/dark color tokens in `app/globals.css`.

- [x] **Step 3: Remove duplicate route-level Inter font setup**

Remove the `next/font/local` declarations and wrapper classes from `app/page.tsx` and `app/create/page.tsx`; keep the existing route components and page behavior unchanged.

- [x] **Step 4: Review font loading and fallbacks**

Open `/` and `/login` in the running app. Confirm Fredoka is used for headings, Nunito for body text, the existing display face still renders brand moments, and there are no third-party font requests.

---

### Task 2: Align the landing page and story creation workspace

**Files:**
- Modify: `wizetale-app/app/landing/globals.css`
- Modify: `wizetale-app/app/globals.css`
- Modify: `wizetale-app/components/slush-landing.tsx`
- Modify: `wizetale-app/app/create/dashboard-client.tsx`

**Interfaces:**
- Consumes: Task 1 root font variables and theme tokens.
- Produces: landing and workspace styles that preserve their layout and content while sharing the app’s typography, color, focus, and motion rules.

- [x] **Step 1: Align landing typography and surfaces**

Use Fredoka for section and card headings, Nunito for navigation and all supporting text, and Fibonacci Display only for the wordmark and the largest hero/interlude moments. Replace isolated Arial styles and tune small copy to remain readable. Retain the current bold, illustrated identity and existing links/content.

- [x] **Step 2: Align the creation workspace styles**

Replace the dashboard’s private font and color definitions in `app/globals.css` with the root tokens. Raise undersized labels/help copy to readable sizes where space allows, keep the form layout intact, and preserve explicit selected, disabled, error, loading, and review states.

- [x] **Step 3: Preserve accessible focus, contrast, and motion behavior**

Ensure the landing and workspace controls have visible focus styles, text remains readable on every accent surface, and decorative ticker/loading animations stop under `prefers-reduced-motion`.

- [x] **Step 4: Review responsive visual behavior**

Inspect `/` and `/create` at 320px, 375px, 768px, and 1440px. Confirm key content and actions remain visible, readable, and free of horizontal overflow.

---

### Task 3: Unify authentication and form components

**Files:**
- Modify: `wizetale-app/components/ui/button.tsx`
- Modify: `wizetale-app/components/ui/card.tsx`
- Modify: `wizetale-app/components/ui/input.tsx`
- Modify: `wizetale-app/components/ui/label.tsx`
- Modify: `wizetale-app/app/login/page.tsx`
- Modify: `wizetale-app/app/register/page.tsx`
- Modify: `wizetale-app/app/reset-password/page.tsx`
- Modify: `wizetale-app/app/reset-password/update/page.tsx`
- Modify: `wizetale-app/app/verify-email/page.tsx`

**Interfaces:**
- Consumes: shared font and theme tokens from Task 1.
- Produces: coherent cards, form controls, alerts, headings, and responsive auth layouts without changing auth state or validation behavior.

- [x] **Step 1: Update shared form primitives to use the app tokens**

Align button, card, input, and label defaults to the shared surfaces, borders, text, and focus ring. Preserve existing variants and component APIs.

- [x] **Step 2: Apply the shared visual system to authentication states**

Update login, registration, password reset/update, and email verification layouts for consistent page backgrounds, readable form copy, clear errors/success states, and comfortable control sizing. Do not change event handlers, validation, routing, or auth calls.

- [x] **Step 3: Review authentication screens**

Inspect `/login`, `/register`, `/reset-password`, `/reset-password/update`, and `/verify-email` at mobile and desktop widths in light and dark themes. Confirm field errors and submission states remain visible and controls retain keyboard focus indicators.

---

### Task 4: Unify story, history, and profile screens

**Files:**
- Modify: `wizetale-app/app/history/page.tsx`
- Modify: `wizetale-app/app/story/[taskId]/page.tsx`
- Modify: `wizetale-app/app/profile/page.tsx`

**Interfaces:**
- Consumes: root typography and theme tokens plus shared form/action styles from Tasks 1 and 3.
- Produces: consistent reading and account surfaces for story cards, recaps, sources, quizzes, profile information, and destructive account actions.

- [x] **Step 1: Align history and generated-story presentation**

Update page backgrounds, navigation, cards, links, buttons, loading/error/empty states, quiz options, and reading typography. Keep story fetching, polling, quiz submission, and navigation behavior unchanged.

- [x] **Step 2: Align the profile and account screen**

Use the same page background, max-width and gutter rules, type hierarchy, buttons, cards, and focus treatments. Keep wrappers route-specific; do not introduce a new layout abstraction. Preserve sign-out and account deletion behavior and make the destructive action visually clear without making it the primary action.

- [x] **Step 3: Review story and account states**

Inspect `/history`, `/story/<taskId>`, and `/profile` in light and dark themes at mobile and desktop widths. Review empty/loading/error/success states where available, long recaps, quiz controls, and destructive account action focus.

---

### Task 5: Run the production build and final visual review

**Files:**
- No additional files; correct any implementation issues found in Tasks 1–4.

- [x] **Step 1: Run the production build**

Run from `wizetale-app/`: `npm run build`

Expected: Next.js completes the production build without errors.

- [x] **Step 2: Review the approved route set and edge conditions**

Recheck the five review-focus items above across the covered routes. Confirm font files and licenses are present, no runtime font-service request occurs, both themes remain readable, and no story/auth/account behavior changed.

- [x] **Step 3: Report the changes and verification results**

Summarize the visual changes, build result, manual route/viewport review, and the lack of Git commit support in this workspace.

**Verification note:** Light mode was visually reviewed on the landing, creation workspace, authentication, history, story, and profile routes across the planned viewport sizes. Dark mode tokens and route styling were inspected in source and covered by design-system checks; a live dark-mode capture was unavailable because no theme control is exposed in the app and the review browser has no color-scheme emulation control.
