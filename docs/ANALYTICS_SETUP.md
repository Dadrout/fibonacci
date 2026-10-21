# Optional Firebase Analytics

Firebase Analytics is disabled by default. Authentication and learner data use Supabase; Firebase is present only for optional legacy analytics.

Do not enable analytics until the owner has approved the privacy notice, child-safety approach, consent behavior, and jurisdictions in which analytics may run. In particular, keep story text, topic names, titles, account identifiers, emails, and generated content out of analytics event parameters.

To enable the current integration after those approvals, configure the Firebase Analytics public app values and set `NEXT_PUBLIC_ENABLE_ANALYTICS=true` in the intended Vercel environment, then redeploy. Keep this setting `false` until the app has the owner-approved consent behavior needed for its audience. Turning it off prevents analytics initialization on the client.

Firebase Analytics data may still have provider-side retention behavior after it has been sent. Account deletion does not delete Firebase Analytics records; disclose and configure that behavior before enabling the integration.
