# Multilingual UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the three existing interface languages easy to use throughout the app and make new story and lesson language defaults follow the chosen interface language.

**Architecture:** Keep the existing `LanguageContext` and `useCopy` translations. Replace the floating language picker with controls in existing page headers and an account page shell; map interface language to content language only when initializing new work. Shared style changes use existing CSS tokens and preserve the landing identity.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, CSS.

**Spec:** `docs/superpowers/specs/2026-10-05-multilingual-ui-design.md`

## Global Constraints

- Support `en`, `ru`, and `kk` interface languages and `en-US`, `ru-RU`, and `kk-KZ` content languages.
- Do not rewrite saved drafts, lessons, sources, or generated results when interface language changes.
- Keep the native language select keyboard accessible; never cover content with it.
- Reuse existing translation data and page shells; no new dependency or wholesale redesign.

## Review Focus

- A saved story draft in a different content language retains its language after interface switching (Task 2).
- A manually chosen content language stays chosen when interface language changes (Task 2).
- A teacher edits an existing lesson without its saved language changing (Task 2).
- The language control remains reachable in mobile navigation and cannot obscure a bottom action (Task 1).
- Kazakh and Russian long labels wrap without clipping or shrinking to unreadable text (Task 3).

---

### Task 1: Place language selection in page navigation

**Files:** Modify `components/language-picker.tsx`, `app/layout.tsx`, `components/slush-landing.tsx`, `components/teacher/shell.tsx`, `app/create/dashboard-client.tsx`, account and learner page headers as needed, and `app/globals.css` / `app/landing/globals.css`.

**Interfaces:** Consume `LanguageContext` via `useLanguage`; preserve `<LanguagePicker />` with an optional class name for page shells.

- [ ] **Step 1: Add a focused UI check** in `scripts/teacher-localization.test.mjs` or a new script asserting the picker is absent from the root fixed overlay and present in the landing, teacher, and learner navigation shells.
- [ ] **Step 2: Run the check** and confirm it fails on the current layout.
- [ ] **Step 3: Move `<LanguagePicker />`** out of `app/layout.tsx`, into existing page headers; provide a shared fallback header for pages without one. Remove fixed positioning and ensure exactly one picker appears per active route.
- [ ] **Step 4: Run the check and typecheck** (`npm run typecheck`); both pass.

### Task 2: Default new content to interface language

**Files:** Create `lib/content-language.ts`; modify `app/create/dashboard-client.tsx`, `components/teacher/lesson-form.tsx`, and focused tests under `scripts/`.

**Interfaces:** Export `contentLanguageFor(language: Language): 'en-US' | 'ru-RU' | 'kk-KZ'`. Inputs come from `useLanguage().language`.

- [ ] **Step 1: Write failing tests** for the three mappings and for story/lesson initialization, draft restoration, manual override, and existing lesson editing.
- [ ] **Step 2: Run the tests** and confirm the English default cases fail.
- [ ] **Step 3: Implement the mapping and form initialization** so only new, untouched work follows interface language. Saved or manually selected content language takes precedence.
- [ ] **Step 4: Run targeted tests and `npm run typecheck`**; both pass.

### Task 3: Consistent layouts and three-language visual review

**Files:** Modify `app/globals.css`, `app/landing/globals.css`, and the page shells touched in Task 1 only where necessary.

**Interfaces:** Use existing color and font tokens and page classes; no new data interfaces.

- [ ] **Step 1: Inspect** landing, account, story studio, story detail, history, profile, and teacher pages at 375px and desktop widths in all three languages. Record concrete clipping, overlap, focus, or spacing failures.
- [ ] **Step 2: Fix verified issues** with shared header, button, heading, and content-width rules. Keep text at readable sizes and preserve keyboard focus styles.
- [ ] **Step 3: Repeat the visual checks** including reduced motion, then run `npm run typecheck`, localization tests, and `npm run build`.
- [ ] **Step 4: Report changes and remaining limitations** with screenshots or reproducible page and viewport details.
