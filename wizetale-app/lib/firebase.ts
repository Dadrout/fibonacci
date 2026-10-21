import { initializeApp, getApps, getApp, type FirebaseApp } from 'firebase/app'
import { getAnalytics, type Analytics } from 'firebase/analytics'

// Firebase is retained only for optional legacy analytics. Fibonacci sign-in,
// stories, history, and generated media use Supabase.
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
}
const hasFirebaseConfig = Boolean(firebaseConfig.apiKey && firebaseConfig.projectId && firebaseConfig.appId)
const app: FirebaseApp | null = hasFirebaseConfig
  ? (getApps().length ? getApp() : initializeApp(firebaseConfig))
  : null

let analyticsInstance: Analytics | null = null
const analyticsExplicitlyEnabled = process.env.NEXT_PUBLIC_ENABLE_ANALYTICS === 'true'
if (app && analyticsExplicitlyEnabled && typeof window !== 'undefined') {
  try { analyticsInstance = getAnalytics(app) } catch { analyticsInstance = null }
}
export const analytics = analyticsInstance
export default app
