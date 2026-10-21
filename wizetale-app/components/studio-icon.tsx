import type { CSSProperties } from 'react'

type IconName = 'arrow' | 'down' | 'check' | 'close' | 'menu' | 'question' | 'edit' | 'book' | 'cards' | 'presentation' | 'plus' | 'sun' | 'moon' | 'mail'
const paths: Record<IconName, React.ReactNode> = {
  arrow: <><path d="M4 12h15M13 6l6 6-6 6"/></>,
  down: <><path d="M12 4v15m-6-6 6 6 6-6"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  close: <path d="m6 6 12 12M6 18 18 6"/>,
  menu: <path d="M4 7h16M4 12h16M4 17h16"/>,
  question: <><path d="M8 8a4 4 0 0 1 8 0c0 3-4 3-4 6"/><path d="M12 18v.1"/></>,
  edit: <><path d="m15 4 5 5M4 20l5-1L21 7l-5-5L4 14v6Z"/></>,
  book: <><path d="M12 6C9 4 5 4 3 5v14c3-1 6-1 9 1 3-2 6-2 9-1V5c-2-1-6-1-9 1v14Z"/></>,
  cards: <><rect x="7" y="6" width="13" height="15" rx="2"/><path d="M15 3H5a2 2 0 0 0-2 2v12M11 11h5m-5 4h3"/></>,
  presentation: <><path d="M3 4h18M5 4v12h14V4m-7 12v5m-4 0 4-3 4 3M8 8h8m-8 4h5"/></>,
  plus: <path d="M5 12h14M12 5v14"/>,
  sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/></>,
  moon: <path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z"/>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/></>,
}
export function StudioIcon({ name, className = '', style }: { name: IconName; className?: string; style?: CSSProperties }) {
  return <svg aria-hidden="true" className={`studio-icon ${className}`} style={style} viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}
