'use client'
import { useCopy } from '@/hooks/use-copy'
import React from 'react'
import { cn } from '@/lib/utils'

interface PasswordStrengthIndicatorProps {
  password: string
  className?: string
}

export const PasswordStrengthIndicator: React.FC<PasswordStrengthIndicatorProps> = ({ 
  password, 
  className 
}) => {
  const c = useCopy()

  const getPasswordStrength = (password: string): { 
    score: number; 
    label: string; 
    color: string 
  } => {
    if (!password) return { score: 0, label: c("Enter password"), color: 'bg-gray-200' }
    
    let score = 0
    
    // Length checks
    if (password.length >= 8) score++
    if (password.length >= 12) score++
    if (password.length >= 16) score++
    
    // Character type checks
    if (/[a-z]/.test(password)) score++
    if (/[A-Z]/.test(password)) score++
    if (/[0-9]/.test(password)) score++
    if (/[^a-zA-Z0-9]/.test(password)) score++
    
    // Common patterns to avoid
    if (!/(.)\1{2,}/.test(password)) score++ // No repeated characters
    if (!/^(123|abc|password)/i.test(password)) score++ // No common patterns
    
    // Determine strength
    if (score <= 3) return { score: 1, label: c("Weak"), color: 'bg-red-500' }
    if (score <= 5) return { score: 2, label: c("Fair"), color: 'bg-orange-500' }
    if (score <= 7) return { score: 3, label: c("Good"), color: 'bg-yellow-500' }
    if (score <= 8) return { score: 4, label: c("Strong"), color: 'bg-sky-500 dark:bg-sky-400' }
    return { score: 5, label: c("Very Strong"), color: 'bg-sky-600 dark:bg-sky-400' }
  }
  
  const strength = getPasswordStrength(password)
  const maxBars = 5
  
  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex gap-1">
        {Array.from({ length: maxBars }).map((_, index) => (
          <div
            key={index}
            className={cn(
              'h-1 flex-1 rounded-full transition-all duration-300',
              index < strength.score ? strength.color : 'bg-gray-200'
            )}
          />
        ))}
      </div>
      {password && (
        <p className={cn(
          'text-xs font-medium',
          strength.score === 1 && 'text-red-600',
          strength.score === 2 && 'text-orange-600',
          strength.score === 3 && 'text-yellow-600',
          strength.score === 4 && 'text-sky-600 dark:text-sky-400',
          strength.score === 5 && 'text-sky-700 dark:text-sky-400'
        )}> {c("Password strength:")} {c(strength.label)}
        </p>
      )}
    </div>
  )
} 
