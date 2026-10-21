'use client'

import type React from "react"
import localFont from "next/font/local"
import { ThemeProvider } from "@/components/theme-provider"
import { copyText } from '@/lib/copy'
import AnalyticsListener from "@/components/analytics-listener"
import { LanguageContext, useLanguageState } from '@/hooks/use-language'
import { AuthContext, useAuthState } from '@/hooks/use-auth'
import { BrainCaptureLayer } from '@/components/brain/brain-capture-layer'
import "./globals.css"
import '@/components/brain/brain.css'

const literata = localFont({
  src: "../public/fonts/Literata-Variable.ttf",
  display: "swap",
  variable: "--font-heading",
  weight: "200 900",
})

const golos = localFont({
  src: "../public/fonts/GolosText-Variable.ttf",
  display: "swap",
  variable: "--font-body",
  weight: "400 900",
})


export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const languageState = useLanguageState()
  const authState = useAuthState()

  return (
    <html lang={languageState.language} suppressHydrationWarning>
      <head>
        <title>{copyText('Fibonacci — Learn any topic step by step', languageState.language)}</title>
        <meta name="description" content={copyText('Fibonacci turns questions and your own material into clear explanations, quizzes, flashcards, presentations, and lessons.', languageState.language)} />
        <link rel="icon" href="/fibonacci-mark.svg" type="image/svg+xml" />
      </head>
      <body className={`${literata.variable} ${golos.variable} app-root min-h-screen`}>
        <LanguageContext.Provider value={languageState}>
          <AuthContext.Provider value={authState}>
            <ThemeProvider attribute="class" defaultTheme="light" enableSystem={true} disableTransitionOnChange={false}>
              <AnalyticsListener />
              <BrainCaptureLayer />
              {children}
            </ThemeProvider>
          </AuthContext.Provider>
        </LanguageContext.Provider>
      </body>
    </html>
  )
}
