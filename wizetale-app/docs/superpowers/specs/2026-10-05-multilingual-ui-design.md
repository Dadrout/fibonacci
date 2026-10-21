# WizeTale multilingual UI and design consistency

## Purpose

Make English, Kazakh, and Russian feel complete across the learner and teacher journeys. The interface language should be easy to change, and a new story or lesson should begin in that language while keeping content language independently editable.

## Current state

The app already has `en`, `ru`, and `kk` interface translations, a persisted language selection, and translated text on all active pages. Story creation and lesson creation each offer the three content languages, but start in English. The global language picker is fixed at the bottom right. The landing page, story studio, and teacher pages have distinct visual styles.

## Experience design

1. Place the interface language control in each page family's header or primary navigation. On narrow screens, place it in the navigation menu or a visible header row. Preserve the native select control, full language names, keyboard access, and saved preference. Remove the fixed overlay.
2. When a user starts a new story or lesson, initialize its content language from the selected interface language (`en` → `en-US`, `ru` → `ru-RU`, `kk` → `kk-KZ`). Keep the content language selector visible and independent. Changing interface language after the user changes the content language must not overwrite that choice. Restored story drafts and existing lessons always retain their saved content language.
3. Keep generated text and user entered content in their own language. Switching interface language only translates interface labels, help text, and status messages; it does not translate or rewrite a draft, source document, lesson, or generated result.
4. Apply shared design rules to headers, page titles, buttons, cards, form labels, focus states, spacing, and content widths while preserving the landing page's playful identity. All three languages must wrap naturally without clipping or tiny text.

## Implementation boundaries

- Reuse the existing language context, `useCopy`, and translation data. Add a small, typed mapping from interface language to content language for new work.
- Render one language control per active page shell: landing, learner pages, account pages, and teacher pages. Avoid duplicate controls in nested layouts.
- Update story and lesson creation defaults. Do not alter saved records, generation APIs, or content already in progress.
- Consolidate repeated style values only where they affect these page shells and controls. Avoid a wholesale redesign of the product.

## Page coverage

- Landing and account: `/`, `/login`, `/register`, `/verify-email`, `/reset-password`, `/reset-password/update`, `/auth/callback`, `/profile`.
- Learner: `/create`, `/history`, `/story/[taskId]`.
- Teacher: `/teacher`, `/teacher/sources`, `/teacher/lessons/[lessonId]`.
- `/landing` routes redirect to their current equivalents and need no separate interface.

## Validation

- Verify every active page in English, Kazakh, and Russian at phone and desktop widths, including long headings, form labels, errors, navigation, and footer content.
- Verify keyboard navigation and focus visibility for the language control and page navigation; check that it never covers content.
- Verify a new story and lesson inherit interface language, manual content language changes persist while the interface language changes, and restored drafts keep their saved language.
- Run the project typecheck and build. Use existing localization tests and add targeted tests only for the new language default behavior.

## Completion criteria

All active page interfaces remain readable in the three languages; switching language works from navigation without covering page actions; new stories and lessons start in the chosen language; saved content is never silently changed.
