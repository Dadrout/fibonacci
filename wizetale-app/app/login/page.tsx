'use client'

import { useCopy } from '@/hooks/use-copy'

import { useState, useRef, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { useAuth } from '@/hooks/use-auth'
import { useLanguage } from '@/hooks/use-language'
import { AuthLanguageNav } from '@/components/auth-language-nav'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, Eye, EyeOff } from 'lucide-react'
import { validateEmail } from '@/lib/user-service'
import { FibonacciMark } from '@/components/fibonacci-mark'

export default function LoginPage() {
  const c = useCopy()

    const router = useRouter()
    const { signIn, loading, signInWithGoogle } = useAuth()
    const { t } = useLanguage()
    
    const [formData, setFormData] = useState({
        email: '',
        password: ''
    })
    
    const errorSummary = useRef<HTMLDivElement>(null)
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState('')
    useEffect(() => { if (error) errorSummary.current?.focus() }, [error])
    const [fieldErrors, setFieldErrors] = useState({
        email: '',
        password: ''
    })

    const validateForm = (): boolean => {
        const errors = {
            email: '',
            password: ''
        }

        // Email validation
        const emailValidation = validateEmail(formData.email)
        if (!emailValidation.isValid) {
            errors.email = emailValidation.error || ''
        }

        // Password validation (just check if exists for login)
        if (!formData.password) {
            errors.password = c("Password is required")
        }

        setFieldErrors(errors)
        return !Object.values(errors).some(error => error !== '')
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        
        if (!validateForm()) {
            setError(c("Please fix the errors below"))
            return
        }

        try {
            setError('')
            await signIn(formData.email, formData.password)
            router.push('/create')
        } catch (error: any) {
            if (error.code === 'auth/user-not-found') {
                setError(c("No account found with this email address"))
            } else if (error.code === 'auth/wrong-password') {
                setError(c("Incorrect password"))
            } else if (error.code === 'auth/invalid-credential') {
                setError(c("Invalid email or password"))
            } else if (error.code === 'auth/too-many-requests') {
                setError(c("Too many failed attempts. Please try again later."))
            } else {
                setError(error instanceof Error ? error.message : c("Failed to sign in. Please try again."))
            }
        }
    }

    const handleInputChange = (field: keyof typeof formData) => (
        e: React.ChangeEvent<HTMLInputElement>
    ) => {
        setFormData(prev => ({ ...prev, [field]: e.target.value }))
        // Clear field error when user starts typing
        setFieldErrors(prev => ({ ...prev, [field]: '' }))
        setError('')
    }

    const handleGoogleSignIn = async () => {
        try {
            setError('')
            await signInWithGoogle()
            router.push('/create')
        } catch (error: any) {
            if (error.code === 'auth/popup-closed-by-user') {
                // User closed the popup, no need to show error
                return
            }
            setError(error instanceof Error ? error.message : c("Failed to sign in with Google"))
        }
    }

    return (
        <div className="auth-page">
            <AuthLanguageNav />
            <Card className="auth-card">
                <CardHeader className="space-y-2 text-center">
                    <div className="mb-[13px] flex justify-center">
                        <FibonacciMark size={48} label={c("Fibonacci Logo")}/>
                    </div>
                    <CardTitle className="text-2xl font-bold">{t.loginTitle}</CardTitle>
                    <CardDescription>
                        {t.loginSubtitle}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form noValidate onSubmit={handleSubmit} className="space-y-5">
                        {error && (
                            <Alert variant="destructive" ref={errorSummary} tabIndex={-1} className="auth-error-summary">
                                <AlertDescription>{c(error)}<ul>{Object.entries(fieldErrors).filter(([, message]) => message).map(([field, message]) => <li key={field}><a href={`#${field}`}>{c(message)}</a></li>)}</ul></AlertDescription>
                            </Alert>
                        )}
                        
                        <div className="space-y-2">
                            <Label htmlFor="email">{t.loginEmailLabel}</Label>
                            <Input
                                id="email"
                                autoComplete="email"
                                aria-invalid={Boolean(fieldErrors.email)}
                                aria-describedby={fieldErrors.email ? 'email-error' : undefined}
                                type="email"
                                placeholder={t.loginEmailPlaceholder}
                                value={formData.email}
                                onChange={handleInputChange('email')}
                                className={fieldErrors.email ? 'border-red-500' : ''}
                                disabled={loading}
                            />
                            {fieldErrors.email && (
                                <p id="email-error" className="text-sm text-destructive">{c(fieldErrors.email)}</p>
                            )}
                        </div>

                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="password">{t.loginPasswordLabel}</Label>
                                <Link 
                                    href="/reset-password" 
                                    className="text-sm font-semibold text-primary hover:underline"
                                >
                                    {t.loginForgotPassword}
                                </Link>
                            </div>
                            <div className="relative">
                                <Input
                                    id="password"
                                autoComplete="current-password"
                                aria-invalid={Boolean(fieldErrors.password)}
                                aria-describedby={fieldErrors.password ? 'password-error' : undefined}
                                    type={showPassword ? 'text' : 'password'}
                                    value={formData.password}
                                    onChange={handleInputChange('password')}
                                    className={fieldErrors.password ? 'border-red-500' : ''}
                                    disabled={loading}
                                />
                                <button
                                    type="button"
                                    aria-label={c(showPassword ? 'Hide password' : 'Show password')}
                                    aria-pressed={showPassword}
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="auth-password-toggle"
                                >
                                    {showPassword ? <EyeOff aria-hidden="true" className="h-4 w-4" /> : <Eye aria-hidden="true" className="h-4 w-4" />}
                                </button>
                            </div>
                            {fieldErrors.password && (
                                <p id="password-error" className="text-sm text-destructive">{c(fieldErrors.password)}</p>
                            )}
                        </div>

                        <Button 
                            type="submit" 
                            className="w-full" 
                            disabled={loading}
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> {c("Signing in...")} </>
                            ) : (
                                t.loginButton
                            )}
                        </Button>
                    </form>

                    <div className="relative my-6">
                        <div className="absolute inset-0 flex items-center">
                            <span className="w-full border-t border-[var(--studio-line)]" />
                        </div>
                        <div className="relative flex justify-center text-xs uppercase">
                            <span className="bg-card px-[13px] tracking-[0.07em] text-muted-foreground">{t.orContinueWith}</span>
                        </div>
                    </div>

                    <Button 
                        type="button" 
                        onClick={handleGoogleSignIn} 
                        className="w-full border border-input bg-card text-card-foreground hover:bg-muted"
                        disabled={loading}
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 533.5 544.3" className="w-4 h-4"><path fill="#4285F4" d="M533.5 278.4c0-17.2-1.3-34.5-4-51.3H272v97.2h146.9c-6.4 34.3-25 63.6-53.2 83.1v68h85.7c50.3-46.3 78.1-114.5 78.1-197z"/><path fill="#34A853" d="M272 544.3c71.6 0 131.7-23.6 175.6-64.3l-85.7-68c-23.8 15.9-54.3 25.2-89.9 25.2-68.9 0-127.4-46.5-148.4-109.2h-88.4v68.8C83.2 483.3 171.9 544.3 272 544.3z"/><path fill="#FBBC05" d="M123.6 324.2c-5.3-15.9-8.3-32.8-8.3-50.2s3-34.3 8.3-50.2v-68.8H35.2C12.6 200.5 0 236.3 0 274s12.6 73.5 35.2 119l88.4-68.8z"/><path fill="#EA4335" d="M272 107.7c38.8 0 73.4 13.3 100.8 39.5l75.6-75.6C403.7 29.6 343.6 0 272 0 171.9 0 83.2 61 35.2 155l88.4 68.8c21-62.7 79.5-116.1 148.4-116.1z"/></svg>
                        {t.loginGoogleButton}
                    </Button>

                    <p className="mt-6 text-center text-base text-muted-foreground">
                        {t.loginRegisterPrompt}{' '}
                        <Link href="/register" className="font-semibold text-primary hover:underline">
                            {t.loginRegisterLink}
                        </Link>
                    </p>
                    {process.env.NEXT_PUBLIC_ENABLE_DASHBOARD_PREVIEW === 'true' && (
                        <Link
                            href="/create?preview=1"
                            className="mt-4 flex min-h-11 items-center justify-center rounded-xl border border-border bg-secondary px-4 text-base font-semibold text-secondary-foreground hover:bg-accent"
                        > {c("Open dashboard preview (no account needed)")} </Link>
                    )}
                </CardContent>
            </Card>
        </div>
    )
} 
