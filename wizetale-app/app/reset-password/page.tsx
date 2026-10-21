'use client'

import { useCopy } from '@/hooks/use-copy'
import { AuthLanguageNav } from '@/components/auth-language-nav'

import { useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useAuth } from '@/hooks/use-auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ArrowLeft, Loader2, CheckCircle } from 'lucide-react'
import { validateEmail } from '@/lib/user-service'
import { FibonacciMark } from '@/components/fibonacci-mark'

export default function ResetPasswordPage() {
  const c = useCopy()

  const { resetPassword } = useAuth()
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate email
    const emailValidation = validateEmail(email)
    if (!emailValidation.isValid) {
      setError(emailValidation.error || c("Invalid email"))
      return
    }

    setLoading(true)
    setError('')

    try {
      await resetPassword(email)
      setSent(true)
    } catch (error: any) {
      if (error.code === 'auth/user-not-found') {
        setError(c("No account found with this email address"))
      } else if (error.code === 'auth/too-many-requests') {
        setError(c("Too many requests. Please wait a few minutes before trying again."))
      } else {
        setError(c("Failed to send reset email. Please try again."))
      }
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <div className="auth-page">
        <AuthLanguageNav />
        <Card className="auth-card">
          <CardHeader className="space-y-2 text-center">
            <div className="mx-auto mb-[13px] flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
              <CheckCircle className="h-6 w-6" />
            </div>
            <CardTitle className="text-2xl font-bold"> {c("Check your email")} </CardTitle>
            <CardDescription> {c("We've sent password reset instructions to")} <strong>{email}</strong>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <Alert>
              <AlertDescription> {c("Click the link in the email to reset your password. The link will expire in 1 hour.")} </AlertDescription>
            </Alert>

            <div className="text-center text-base leading-relaxed text-muted-foreground">
              <p> {c("Didn't receive the email? Check your spam folder.")} </p>
              <p className="mt-2">
                <button
                  onClick={() => {
                    setSent(false)
                    setEmail('')
                  }}
                  className="font-semibold text-primary hover:underline"
                > {c("Try with a different email")} </button>
              </p>
            </div>

            <Link href="/login">
              <Button variant="ghost" className="w-full">
                <ArrowLeft className="mr-2 h-4 w-4" /> {c("Back to login")} </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="auth-page">
      <AuthLanguageNav />
      <Card className="auth-card">
        <CardHeader className="space-y-2 text-center">
          <div className="mb-[13px] flex justify-center">
            <FibonacciMark size={48} label={c("Fibonacci Logo")}/>
          </div>
          <CardTitle className="text-2xl font-bold"> {c("Reset your password")} </CardTitle>
          <CardDescription> {c("Enter your email address and we'll send you instructions to reset your password")} </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{c(error)}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <Label htmlFor="email"> {c("Email address")} </Label>
              <Input
                id="email"
                type="email"
                placeholder="john@example.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  setError('')
                }}
                disabled={loading}
                required
              />
            </div>

            <Button 
              type="submit" 
              className="w-full" 
              disabled={loading || !email}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> {c("Sending...")} </>
              ) : (
                c("Send reset instructions")
              )}
            </Button>
          </form>

          <div className="mt-[21px] text-center">
            <Link href="/login" className="inline-flex min-h-11 items-center gap-1 text-base font-semibold text-muted-foreground hover:text-foreground">
              <ArrowLeft className="inline-block mr-1 h-3 w-3" /> {c("Back to login")} </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
} 
