export interface UserValidation {
  isValid: boolean
  errors: { username?: string; email?: string; password?: string; displayName?: string }
}

export const validateUsername = async (username: string): Promise<{ isValid: boolean; error?: string }> => {
  if (!username || username.length < 3) return { isValid: false, error: 'Username must be at least 3 characters long' }
  if (username.length > 20) return { isValid: false, error: 'Username must be less than 20 characters' }
  if (!/^[a-zA-Z0-9_]+$/.test(username)) return { isValid: false, error: 'Username can only contain letters, numbers, and underscores' }
  return { isValid: true }
}

export const validateEmail = (email: string): { isValid: boolean; error?: string } => {
  if (!email) return { isValid: false, error: 'Email is required' }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return { isValid: false, error: 'Invalid email format' }
  return { isValid: true }
}

export const validatePassword = (password: string): { isValid: boolean; error?: string; strength?: 'weak' | 'medium' | 'strong' } => {
  if (!password || password.length < 8) return { isValid: false, error: 'Password must be at least 8 characters long' }
  let score = 0
  if (/[a-z]/.test(password)) score++
  if (/[A-Z]/.test(password)) score++
  if (/[0-9]/.test(password)) score++
  if (/[^a-zA-Z0-9]/.test(password)) score++
  if (password.length >= 12) score++
  if (password.length >= 16) score++
  const strength = score >= 5 ? 'strong' : score >= 3 ? 'medium' : 'weak'
  return strength === 'weak' ? { isValid: false, strength, error: 'Password is too weak. Use uppercase, lowercase, numbers, and symbols' } : { isValid: true, strength }
}
