# Production release checklist

## Before deploying

- [ ] API `.env` contains real Supabase, Redis, media storage, AI, and selected speech-provider values; file permissions are restricted.
- [ ] Any credentials present in tracked Certbot or service-account files have been rotated, and secret files are excluded from the release tree. History cleanup requires a separate reviewed change after rotation.
- [ ] `GEMINI_BILLING_TIER=paid` reflects the actual provider account, and budget/quota alerts are configured.
- [ ] Latest Supabase schema (including `account_deletion_locks`), approved knowledge seed, Auth email settings, RLS policies, and private media bucket are configured.
- [ ] DNS for `api.wizetale.com` points to the API host; ports 80 and 443 are reachable.
- [ ] Initial certificate was obtained through the bootstrap Nginx configuration.
- [ ] Vercel Production variables include the public Supabase URL/key and server-only `BACKEND_API_URL=https://api.wizetale.com`.
- [ ] Privacy, terms, age/parent-consent, data-retention, and incident-response gates in [`PUBLIC_LAUNCH_GATES.md`](PUBLIC_LAUNCH_GATES.md) have owner approval and are implemented.
- [ ] CI is green for the exact commit being released.

## Release

- [ ] Run `./deploy.sh` from the intended checkout with `DEPLOY_HOST`, `DEPLOY_USER`, and `REMOTE_PROJECT_DIR` set.
- [ ] Wait for `https://api.wizetale.com/health` and the Vercel deployment to pass their health checks.
- [ ] Verify sign-in, story draft creation, generation, media playback, quiz saving, and account deletion with a test learner.
- [ ] Check API and worker logs, provider usage/billing, Redis persistence, database backups, and alert delivery.

## Recovery

- [ ] Keep the previous Vercel deployment available for instant rollback.
- [ ] Keep a restorable database backup and private media backup/retention plan.
- [ ] Revert by deploying the previous known-good commit; never use a hard reset that discards uncommitted host changes.

This checklist does not represent a launch approval by itself. Marking all items complete requires live service and policy verification.
