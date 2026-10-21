# Gemini documentation review for local free-tier use

Reviewed on 2026-10-04, before replacing the private key or changing Gemini settings. This covers the documentation relevant to this project's text, structured resources, images, authentication, quotas, errors, billing and release gates; it is not a claim to have read every SDK example or unrelated product guide.

## Models and features

Google's [pricing table](https://ai.google.dev/gemini-api/docs/pricing) lists free text input/output for `gemini-3.1-flash-lite` and `gemini-3-flash-preview`, the app's existing primary/fallback. Keep these models for this configuration. `gemini-3.1-flash-lite-image` has no free API tier. AI Studio access does not imply free image API access.

Local settings now declare `GEMINI_BILLING_TIER=free`, `ENABLE_GEMINI_IMAGE=false`, and `GENERATION_MAX_IMAGES_PER_STORY=0`. The existing renderer generates placeholder scene cards without an image API request. Narration providers are unchanged. Production still has its existing paid-tier requirement; this local setup does not establish production readiness.

Sources: [models](https://ai.google.dev/gemini-api/docs/models), [image generation](https://ai.google.dev/gemini-api/docs/image-generation).

## Authentication and transport

The [API key guide](https://ai.google.dev/gemini-api/docs/api-key) describes standard and authorization keys, with new AI Studio keys created as authorization keys. Keep the supplied key opaque; do not reject it for lacking the older key prefix. The app sends it in `x-goog-api-key` on server-side requests. Both private server environment files were updated with owner-only permissions. The supplied key is absent from frontend environment files.

The current `generateContent` transport remains documented in the [REST reference](https://ai.google.dev/api/generate-content). No SDK or endpoint migration is required to replace this key. Model listing alone does not establish generation access; generation was checked separately. Rotate the key shared in chat before public use.

## Quotas and billing

[Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) are per project, not per key. RPM, TPM and daily limits vary by model/project; daily requests reset at midnight Pacific time. Read actual limits in AI Studio rather than hardcoding a universal free allowance. The app's user/action limits are separate from Google's shared quota.

The [billing guide](https://ai.google.dev/gemini-api/docs/billing) distinguishes free API projects from paid projects and free AI Studio access. A depleted paid prepayment account does not automatically become free. The previous key's 402 therefore did not prove that this newly supplied key would require a credit purchase. No billing settings or purchases were changed. The free-tier declaration follows the owner's statement; successful calls alone do not prove billing status.

## Resource format and errors

The app requests JSON MIME output, includes the Pydantic schema in its prompt, then validates the returned JSON and resource-specific rules. This is prompt-guided JSON, not provider-enforced JSON Schema. The [structured output guide](https://ai.google.dev/gemini-api/docs/structured-output) supports schema-constrained output with a subset of JSON Schema; complex schemas can be rejected. Adding that stricter request contract would require separate compatibility tests.

The [troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting) recommends bounded backoff/jitter for transient failures and no retries for configuration/billing errors such as 400, 402 or 403. The current app attempts one primary and one fallback model; it does not implement general backoff. No retry behavior was changed during this credential setup.

## Launch constraints

The current [Gemini API terms](https://ai.google.dev/gemini-api/terms) say unpaid inputs/outputs may be used to improve Google products and reviewed by humans; personal, confidential and sensitive information must not be submitted. Local verification uses fictional, nonpersonal lesson data. Do not put student names, records or private school documents into these free-tier checks.

The same terms restrict API clients directed toward or likely to be accessed by under-18s. Paid billing alone does not remove that age restriction. The existing learner-facing product needs an owner/provider review before launch; adult teacher preparation and student-facing access need separate assessment. EEA/UK/Swiss API availability also has a paid-services restriction.

## Live verification

- New key: model listing HTTP 200.
- Primary `gemini-3.1-flash-lite`: minimal text generation HTTP 200 with text returned.
- Fallback `gemini-3-flash-preview`: minimal text generation HTTP 200 with text returned.
- App configuration: local development/free declaration confirmed; paid image calls disabled.
- Teacher resource checks and service restart results are recorded in `LOCAL_SETUP.md` after completion.
