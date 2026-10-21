"use client"

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { useAuth } from '@/hooks/use-auth'
import { useCopy } from '@/hooks/use-copy'
import { AuthLanguageNav } from '@/components/auth-language-nav'
import { useLanguage } from '@/hooks/use-language'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, Eye, EyeOff, Check, X } from 'lucide-react'
import { PasswordStrengthIndicator } from '@/components/password-strength-indicator'
import { 
  validateEmail, 
  validatePassword, 
  validateUsername 
} from '@/lib/user-service'
import { FibonacciMark } from '@/components/fibonacci-mark'

export default function RegisterPage() {
    const router = useRouter()
    const { signUp, loading, signInWithGoogle } = useAuth()
    const { t } = useLanguage()
    const c = useCopy()
    const [role, setRole] = useState<'learner'|'teacher'>('learner')
    
    const [formData, setFormData] = useState({
        email: '',
        password: '',
        confirmPassword: '',
        username: '',
        displayName: ''
    })
    
    const errorSummary = useRef<HTMLDivElement>(null)
    const [showPassword, setShowPassword] = useState(false)
    const [showConfirmPassword, setShowConfirmPassword] = useState(false)
    const [error, setError] = useState('')
    useEffect(() => { if (error) errorSummary.current?.focus() }, [error])
    const [isCheckingUsername, setIsCheckingUsername] = useState(false)
    const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null)
    const [fieldErrors, setFieldErrors] = useState({
        email: '',
        password: '',
        confirmPassword: '',
        username: '',
        displayName: ''
    })

    // Debounced username check
    useEffect(() => {
        if (!formData.username || formData.username.length < 3) {
            setUsernameAvailable(null)
            return
        }

        const timer = setTimeout(async () => {
            setIsCheckingUsername(true)
            const result = await validateUsername(formData.username)
            setUsernameAvailable(result.isValid)
            setFieldErrors(prev => ({ ...prev, username: result.error || '' }))
            setIsCheckingUsername(false)
        }, 500)

        return () => clearTimeout(timer)
    }, [formData.username])

    const validateForm = (): boolean => {
        const errors = {
            email: '',
            password: '',
            confirmPassword: '',
            username: '',
            displayName: ''
        }

        // Email validation
        const emailValidation = validateEmail(formData.email)
        if (!emailValidation.isValid) {
            errors.email = emailValidation.error || ''
        }

        // Password validation
        const passwordValidation = validatePassword(formData.password)
        if (!passwordValidation.isValid) {
            errors.password = passwordValidation.error || ''
        }

        // Confirm password
        if (formData.password !== formData.confirmPassword) {
            errors.confirmPassword = c("Passwords do not match")
        }

        // Username validation (already checked in useEffect)
        if (!formData.username) {
            errors.username = c("Username is required")
        } else if (usernameAvailable === false) {
            errors.username = c("Username is already taken")
        }

        // Display name validation (optional but has length limit)
        if (formData.displayName && formData.displayName.length > 50) {
            errors.displayName = c("Display name must be less than 50 characters")
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
            await signUp(
                formData.email, 
                formData.password, 
                formData.username,
                formData.displayName || formData.username,
                role
            )
            router.push(`/verify-email?email=${encodeURIComponent(formData.email)}`)
        } catch (error: any) {
            if (error.code === 'auth/email-already-in-use') {
                setError(c("An account with this email already exists"))
            } else if (error.code === 'auth/weak-password') {
                setError(c("Password is too weak"))
            } else {
                setError(error instanceof Error ? error.message : c("Failed to create account. Please try again."))
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
            await signInWithGoogle(role === 'teacher' ? '/teacher' : '/create')
        } catch (error: any) {
            if (error.code === 'auth/popup-closed-by-user') {
                return // Don't show an error if the user closes the popup
            }
            setError(error instanceof Error ? error.message : c("Failed to sign in with Google. Please try again."))
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
                    <CardTitle className="text-2xl font-bold">{t.registerTitle}</CardTitle>
                    <CardDescription>
                        {t.registerSubtitle}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form noValidate onSubmit={handleSubmit} className="space-y-5">
                        <label className="block text-base font-semibold">{c('I am a')}
                          <select className="mt-2 h-11 w-full rounded-xl border border-input bg-background px-3" value={role} onChange={e=>setRole(e.target.value as 'learner'|'teacher')} disabled={loading}>
                            <option value="learner">{c('Learner')}</option><option value="teacher">{c('Teacher')}</option>
                          </select>
                        </label>
                        {error && (
                            <Alert variant="destructive" ref={errorSummary} tabIndex={-1} className="auth-error-summary">
                                <AlertDescription>{c(error)}<ul>{Object.entries(fieldErrors).filter(([, message]) => message).map(([field, message]) => <li key={field}><a href={`#${field}`}>{c(message)}</a></li>)}</ul></AlertDescription>
                            </Alert>
                        )}
                        
                        <div className="space-y-2">
                            <Label htmlFor="username">{t.registerUsernameLabel}</Label>
                            <div className="relative">
                                <Input
                                    id="username"
                                autoComplete="username"
                                aria-invalid={Boolean(fieldErrors.username)}
                                aria-describedby={fieldErrors.username ? 'username-error' : undefined}
                                    placeholder={t.registerUsernamePlaceholder}
                                    value={formData.username}
                                    onChange={handleInputChange('username')}
                                    className={fieldErrors.username ? 'border-red-500' : ''}
                                    disabled={loading}
                                />
                                {isCheckingUsername && (
                                    <Loader2 className="absolute right-3 top-3 h-4 w-4 animate-spin text-muted-foreground" />
                                )}
                                {!isCheckingUsername && formData.username.length >= 3 && (
                                    usernameAvailable ? (
                                        <Check className="absolute right-3 top-3 h-4 w-4 text-sky-600 dark:text-sky-400" />
                                    ) : (
                                        <X className="absolute right-3 top-3 h-4 w-4 text-destructive" />
                                    )
                                )}
                            </div>
                            {fieldErrors.username && (
                                <p id="username-error" className="text-sm text-destructive">{c(fieldErrors.username)}</p>
                            )}
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="email">{t.registerEmailLabel}</Label>
                            <Input
                                id="email"
                                autoComplete="email"
                                aria-invalid={Boolean(fieldErrors.email)}
                                aria-describedby={fieldErrors.email ? 'email-error' : undefined}
                                type="email"
                                placeholder={t.registerEmailPlaceholder}
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
                            <Label htmlFor="displayName">{t.registerDisplayNameLabel}</Label>
                            <Input
                                id="displayName"
                                autoComplete="name"
                                aria-invalid={Boolean(fieldErrors.displayName)}
                                aria-describedby={fieldErrors.displayName ? 'displayName-error' : undefined}
                                placeholder={t.registerDisplayNamePlaceholder}
                                value={formData.displayName}
                                onChange={handleInputChange('displayName')}
                                className={fieldErrors.displayName ? 'border-red-500' : ''}
                                disabled={loading}
                            />
                            {fieldErrors.displayName && (
                                <p id="displayName-error" className="text-sm text-destructive">{c(fieldErrors.displayName)}</p>
                            )}
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="password">{t.registerPasswordLabel}</Label>
                            <div className="relative">
                                <Input
                                    id="password"
                                autoComplete="new-password"
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
                            <PasswordStrengthIndicator password={formData.password} />
                            {fieldErrors.password && (
                                <p id="password-error" className="text-sm text-destructive">{c(fieldErrors.password)}</p>
                            )}
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="confirmPassword">{t.registerConfirmPasswordLabel}</Label>
                            <div className="relative">
                                <Input
                                    id="confirmPassword"
                                autoComplete="new-password"
                                aria-invalid={Boolean(fieldErrors.confirmPassword)}
                                aria-describedby={fieldErrors.confirmPassword ? 'confirmPassword-error' : undefined}
                                    type={showConfirmPassword ? 'text' : 'password'}
                                    value={formData.confirmPassword}
                                    onChange={handleInputChange('confirmPassword')}
                                    className={fieldErrors.confirmPassword ? 'border-red-500' : ''}
                                    disabled={loading}
                                />
                                <button
                                    type="button"
                                    aria-label={c(showConfirmPassword ? 'Hide confirmation password' : 'Show confirmation password')}
                                    aria-pressed={showConfirmPassword}
                                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                    className="auth-password-toggle"
                                >
                                    {showConfirmPassword ? <EyeOff aria-hidden="true" className="h-4 w-4" /> : <Eye aria-hidden="true" className="h-4 w-4" />}
                                </button>
                            </div>
                            {fieldErrors.confirmPassword && (
                                <p id="confirmPassword-error" className="text-sm text-destructive">{c(fieldErrors.confirmPassword)}</p>
                            )}
                        </div>

                        <Button 
                            type="submit" 
                            className="w-full" 
                            disabled={loading || isCheckingUsername || usernameAvailable === false}
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> {c("Creating account...")} </>
                            ) : (
                                t.registerButton
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
                        {t.registerGoogleButton}
                    </Button>

                    <p className="mt-6 text-center text-base text-muted-foreground">
                        {t.registerLoginPrompt}{' '}
                        <Link href="/login" className="font-semibold text-primary hover:underline">
                            {t.registerLoginLink}
                        </Link>
                    </p>
                </CardContent>
            </Card>
        </div>
    )
}
