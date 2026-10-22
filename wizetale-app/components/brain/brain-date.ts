/*
 * Dates for the Brain in en / ru / kk. Some browsers ship without Kazakh date data and
 * silently fall back to English ("Oct 22"), so Kazakh has a built-in fallback that
 * matches the standard Kazakh format ("22 қаз.", "22 қаз., бс", "22 қаз., 10:05").
 * Pure: no runtime imports, so Node tests can load it directly.
 */

const KK_MONTHS = ['қаң.', 'ақп.', 'нау.', 'сәу.', 'мам.', 'мау.', 'шіл.', 'там.', 'қыр.', 'қаз.', 'қар.', 'жел.']
const KK_WEEKDAYS = ['жс', 'дс', 'сс', 'ср', 'бс', 'жм', 'сб']

let kazakhSupported: boolean | null = null

function browserHasKazakh(): boolean {
  if (kazakhSupported === null) {
    try {
      kazakhSupported = new Intl.DateTimeFormat('kk').resolvedOptions().locale.startsWith('kk')
    } catch {
      kazakhSupported = false
    }
  }
  return kazakhSupported
}

const pad = (value: number) => String(value).padStart(2, '0')

function kazakhFallback(date: Date, options: Intl.DateTimeFormatOptions): string {
  const utc = options.timeZone === 'UTC'
  const day = utc ? date.getUTCDate() : date.getDate()
  const month = utc ? date.getUTCMonth() : date.getMonth()
  if (!options.month) return `${pad(day)}.${pad(month + 1)}.${utc ? date.getUTCFullYear() : date.getFullYear()}`
  let text = `${day} ${KK_MONTHS[month]}`
  if (options.weekday) text += `, ${KK_WEEKDAYS[utc ? date.getUTCDay() : date.getDay()]}`
  if (options.hour) text += `, ${pad(utc ? date.getUTCHours() : date.getHours())}:${pad(utc ? date.getUTCMinutes() : date.getMinutes())}`
  return text
}

/** Format a date for the UI language ('en' | 'ru' | 'kk' or a full locale like 'kk-KZ'). */
export function formatBrainDate(date: Date, locale: string, options: Intl.DateTimeFormatOptions = {}): string {
  if (Number.isNaN(date.valueOf())) return ''
  if (locale.toLowerCase().startsWith('kk') && !browserHasKazakh()) return kazakhFallback(date, options)
  return new Intl.DateTimeFormat(locale, options).format(date)
}

/** Test hook: pretend the browser lacks (false) or has (true) Kazakh date data. */
export function setKazakhSupportForTests(value: boolean | null): void {
  kazakhSupported = value
}
