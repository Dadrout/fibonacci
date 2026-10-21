# TaleSpark UI redesign — 19 October 2026

## Research

Public pages were actually opened in the configured in-app browser. The observations below are limited to their public entry pages; no claim is made to have tested their authenticated products.

| Reference | Observed principle | Application to TaleSpark |
| --- | --- | --- |
| [Are.na](https://www.are.na/) | Narrow reading measure, plain language, content organization explained through tasks | Put the learning task before decoration; use readable supporting text |
| [Readwise Reader](https://www.readwise.io/read) | A direct product promise and immediate product preview | Put an inspectable example beside the main action |
| [Craft](https://www.craft.do/) | Editorial serif hierarchy and expressive, coherent materials | Use a serif for curiosity and narrative, with quieter product controls |
| [Brilliant](https://www.brilliant.org/) | Learner versus parent/teacher entry, interactive learning content in the hero | Give teachers a distinct path and make the sample useful |
| [Khan Academy](https://www.khanacademy.org/) | Role-based entry, explicit next actions, benefits explained in user terms | Clear teacher route and action-oriented learning flow |
| [Awwwards](https://www.awwwards.com/) | Typographic scale and strong compositional hierarchy in its featured project presentation | Commit to a recognizable typographic identity without importing experimental navigation |
| [Milanote](https://milanote.com/) | Serif headline, concise task promise, product board shown immediately | Treat content organization as part of the experience |
| [Duolingo](https://www.duolingo.com/) | Clear new-user/returning-user actions and visible language selection | Keep sign-in, language, and the main learning action easy to locate |

Notion was opened but rendered without its expected styling, so it was excluded as visual evidence. Some additional navigations did not yield usable evidence and are not counted. These references informed composition and task hierarchy; no copied images or artwork ship in the app.

The ui-ux-pro-max design-system and Next.js stack searches were run. The generic Outfit/Work Sans result was unsuitable for the required Cyrillic coverage and was replaced with verified locally hosted Literata and Golos Text. The focused `error summary validation` UX search guided the account form changes.

## Existing interface and changes

Source inspection covered the landing, learner shell, draft lifecycle, story viewer/library, study tools, teacher lesson/source/resource workflows, account, registration, login, password reset, verification, shared controls, theme, and localization. Browser inspection covered accessible public and local-preview surfaces. Authenticated teacher and learner generation require a connected test account and backend.

- **Landing:** oversized ribbon art and a moving ticker dominated the first impression. Replaced them with an editorial introduction and a clearly labeled sample story, recap, and quiz with corrective feedback. The labeled Silk Road schematic explains connection; it is explicitly illustrative.
- **Learner workflow:** shared setup and the active editor occupied a long desktop stack. Added a two-column workbench that keeps topic and format close to the active material. Mobile layout stacks logically and compacts subject/language fields. Optional topic suggestions use native disclosure. Saved work has a direct toggle. The underlying draft, generation, storage, route, and format-switching behavior remains in place.
- **Story feedback:** an empty question disabled generation without enough nearby guidance. Added an explicit instruction; raised supporting text sizes and themed review, error, and success states.
- **Navigation:** preserved active-page semantics and all existing routes. Added consistent theme controls to marketing, learner, study, teacher, and auth headers. Retained the original brand asset.
- **Account forms:** password visibility buttons lacked accessible labels, and validation lacked a linked, focused summary. Added action labels, pressed state, 44px controls, password-manager autocomplete, invalid field relationships, retained inline errors, and a summary that receives focus after failure.
- **Design system:** replaced the varied purple, blue, and sticker palettes with paper, green, sage, and vermilion; shared component tokens map onto existing semantic contracts. Bundled fonts and licenses; verified Russian and Kazakh character coverage. Removed the old Cyrillic font override.
- **Teacher and study surfaces:** shared navigation, lesson tiles, source rows, resource controls, working surfaces, typography, states, and buttons inherit the new system. Business logic and source/content contracts were not replaced.
- **Email verification:** replaced an emoji with a small custom SVG mail symbol.

## Visual direction and implementation

See [DESIGN.md](../DESIGN.md) and [design-system/talespark/MASTER.md](../design-system/talespark/MASTER.md) for tokens, typography, layout, and interaction guidance.

Main implementation files:

- `wizetale-app/components/slush-landing.tsx`, `app/landing/globals.css`: replacement landing and interactive sample.
- `components/studio-icon.tsx`, `components/theme-toggle.tsx`: authored control artwork and shared appearance control.
- `app/layout.tsx`, `app/globals.css`: local fonts, light/dark tokens, account surfaces and interaction primitives.
- `app/create/student-workspace-client.tsx`, `student-workspace.css`, `dashboard-client.tsx`: learner layout, suggestions, saved-work access, and story feedback.
- `app/teacher/teacher.css`, teacher/study shells: common application chrome and working surfaces.
- `app/login/page.tsx`, `app/register/page.tsx`, `app/verify-email/page.tsx`, auth header: accessible account interactions.
- `lib/copy.ts`: Russian and Kazakh translations for new copy.

No new npm dependency was added. No deployment was performed. Existing authentication, backend proxies, generation hooks, ownership, and storage logic remain intact.

## Verification

- Production build: passed (`npm run build`, outside sandbox because the sandbox blocked Next's TypeScript subprocess).
- TypeScript: passed (`npm run typecheck`).
- Existing regression suite: all 17 test files passed with `node --experimental-strip-types --test scripts/*.test.cjs scripts/*.test.mjs`. Typography assertions were updated to the replacement design; the teacher test now accepts the semantic foreground mapping.
- Mechanical design detector: returned an empty findings array for the changed targets.
- Browser: sample story/recap/quiz selection; wrong and correct answers; topic suggestion and sample draft creation; draft edits retained across format switches; disabled empty-topic action; light/dark switching; English/Russian/Kazakh copy; mobile menu and anchor navigation; sign-in and registration failure summaries; error summary focus and field linkage; password visibility labels/state; signed-out teacher entry.
- Responsive inspection: 375×812 phone, 768×1024 tablet, 812×375 landscape, and default desktop viewport. No document horizontal overflow was observed in the checked views. Long Kazakh headings wrap and use Literata after removing a legacy fallback rule.
- Core contrast pairs measured from the actual tokens meet normal-text 4.5:1, including muted text on sage (4.56:1). Working controls have stronger boundaries, visible focus, and native disabled states.
- Reduced-motion rules were checked in the styles and regression suite; OS-level reduced-motion emulation was unavailable through the browser API. The existing `MotionConfig reducedMotion="user"` remains in place.

### Remaining verification limits

Local Supabase session restoration fails to fetch, and no authenticated test account was supplied. Real sign-in, saving, generated video, teacher resource generation, file uploads, printing, and populated authenticated data were not tested end to end. Local-preview tests use the existing sample-only feature flag. These limitations prevent a full production-readiness claim.

## Screenshots

All captures are in [artifacts/redesign](../artifacts/redesign). The original landing capture precedes the replacement. Later screenshots include the default desktop, full landing, phone, Kazakh phone, learner editor light/dark, tablet, signed-out teacher, and auth validation. The development-tools badge is part of the local development environment.

- [Before landing](../artifacts/redesign/before-landing.jpg)
- [After landing](../artifacts/redesign/after-landing-desktop.jpg)
- [Full landing](../artifacts/redesign/after-landing-full.jpg)
- [Phone landing](../artifacts/redesign/after-landing-mobile.jpg)
- [Kazakh phone](../artifacts/redesign/after-kazakh-mobile.jpg)
- [Learner editor](../artifacts/redesign/after-studio-desktop.jpg)
- [Dark learner editor](../artifacts/redesign/after-studio-dark.jpg)
- [Phone workspace](../artifacts/redesign/after-studio-mobile.jpg)
- [Tablet workspace](../artifacts/redesign/after-studio-tablet.jpg)
- [Teacher entry](../artifacts/redesign/after-teacher-signed-out.jpg)
- [Auth validation](../artifacts/redesign/after-login-errors.jpg)
