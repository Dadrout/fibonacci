# Fibonacci (formerly TaleSpark)

Fibonacci helps people understand material by turning it into a path of ideas, each step building on the last. Today it turns educational questions into editable learning stories for ages 10–18 and helps teachers prepare private K–12 lesson materials. It supports English, Russian, and Kazakh; the interface language and generated-material language can differ.

The learner workspace supports story scripts and video generation, quizzes, flashcards, presentations, and saved work. The teacher workspace supports lessons, source documents, resource generation and editing, and print/presentation workflows. Learners review story drafts before choosing video generation.

The frontend is an existing Next.js 16 / React 19 app in `wizetale-app`. Authentication uses Supabase; server routes proxy to the existing FastAPI/Celery backend. This redesign preserves those integrations and private ownership rules. The existing local preview is opt-in, explicitly labeled, and uses sample content without creating saved work.

The redesign brief calls for a distinctive identity, useful visuals, simpler task completion, practical accessibility, responsive behavior, both existing themes, maintained localization, and actual implementation. No stock imagery, fake metrics, invented saved work, or replacement of functional workflows with static mockups.


The longer-term direction (source analysis, the learning path, citations at sentence level, and the roadmap) is in `docs/fibonacci-plan.html`. Internal service names (`wizetale-app`, `wizetale-api`, Docker images, domain) are unchanged until the domain and trademark are settled.
