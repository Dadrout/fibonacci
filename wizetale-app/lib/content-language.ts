import type { Language } from './i18n'

export type ContentLanguage = 'en-US' | 'ru-RU' | 'kk-KZ'

const contentLanguages: Record<Language, ContentLanguage> = {
  en: 'en-US',
  ru: 'ru-RU',
  kk: 'kk-KZ',
}

export function contentLanguageFor(language: Language): ContentLanguage {
  return contentLanguages[language]
}
