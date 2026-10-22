# Google sign-in through Supabase Auth

Fibonacci uses Supabase Auth for sign-in. Google OAuth is configured in Supabase; Firebase Authentication is not used.

1. In Google Cloud Console, create a web OAuth client and add the Supabase callback URL shown in **Supabase Dashboard → Authentication → Providers → Google**. It follows the form `https://<project-ref>.supabase.co/auth/v1/callback`.
2. Enable Google in Supabase Auth and enter the Google client ID and secret there. Keep the client secret server-side in Supabase settings.
3. In **Supabase Dashboard → Authentication → URL Configuration**, set the production Site URL and allow the exact redirect URL `https://wizetale.com/auth/callback`. Add local development redirects only for the local origins you use.
4. In Google OAuth consent-screen settings, configure the app name, support contact, scopes, and publishing status. Obtain any required verification before public use.
5. Verify sign-in and sign-out on a production test account. Fibonacci uses a redirect flow and returns through `/auth/callback`.

Do not add Google or Supabase secrets to `NEXT_PUBLIC_` variables. See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the production environment-variable list.
