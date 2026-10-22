'use client'

/*
 * Telegram connect (board row A8). Built by Claude while Codex was paused; Astra owns the design.
 * Bot status → one-time 6-digit code + QR of the deep link + countdown → linked state (live via
 * the `telegram.linked` event) → unlink.
 */
import { useCallback, useEffect, useState } from 'react'
import QRCode from 'qrcode'
import { CheckCircle2, ExternalLink, RefreshCw, Send, TriangleAlert, Unlink } from 'lucide-react'
import { useBrainEvents } from '@/hooks/use-brain-api'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import './brain-courses.css'
import { formatBrainDate } from './brain-date'
import type { BrainApi } from '@/lib/brain-api'
import type { TelegramLinkCode, TelegramStatus } from '@/lib/brain-types'

export function BrainTelegram({ api }: { api: BrainApi }) {
  const c = useCopy()
  const { language } = useLanguage()
  const [status, setStatus] = useState<TelegramStatus | null>(null)
  const [code, setCode] = useState<TelegramLinkCode | null>(null)
  const [qr, setQr] = useState<string | null>(null)
  const [qrFailed, setQrFailed] = useState(false)
  const [statusFailed, setStatusFailed] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setStatusFailed(false)
    setError(null)
    try {
      setStatus(await api.telegramStatus())
      setError(null)
    } catch {
      setStatusFailed(true)
      setError('Telegram status could not load.')
    }
  }, [api])

  useEffect(() => { void load() }, [load])

  useBrainEvents((event) => {
    if (event.type === 'telegram.linked') {
      setStatus(event.telegram)
      setStatusFailed(false)
      setError(null)
      setCode(null)
    }
  })

  useEffect(() => {
    if (!code) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [code])

  useEffect(() => {
    let alive = true
    setQr(null)
    setQrFailed(false)
    if (!code) { setQr(null); return }
    QRCode.toDataURL(code.deep_link, { margin: 1, width: 232, errorCorrectionLevel: 'M', color: { dark: '#14231c', light: '#ffffff' } })
      .then(url => { if (alive) setQr(url) })
      .catch(() => { if (alive) setQrFailed(true) })
    return () => { alive = false }
  }, [code])

  const connect = async () => {
    setBusy(true)
    setError(null)
    try {
      setCode(await api.telegramLinkCode())
      setNow(Date.now())
    } catch {
      setError('A code could not be created. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const unlink = async () => {
    setBusy(true)
    try {
      await api.telegramUnlink()
      await load()
    } catch {
      setError('Telegram could not be disconnected. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const secondsLeft = code ? Math.max(0, Math.round((Date.parse(code.expires_at) - now) / 1000)) : 0
  const expired = Boolean(code) && secondsLeft === 0
  const countdown = `${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, '0')}`

  return <section className="brain-telegram" aria-labelledby="brain-telegram-title">
    <div className="brain-inbox-heading">
      <div>
        <p className="brain-section-kicker">{c('Capture from your chats')}</p>
        <h2 id="brain-telegram-title">{c('Send it from Telegram.')}</h2>
        <p>{c('Forward slide photos, PDFs, lecture links, and voice notes to the Fibonacci bot. They are filed into your Brain within seconds.')}</p>
      </div>
    </div>

    {error && <div className="brain-telegram-error">
      <p className="brain-item-action-error" role="alert"><TriangleAlert size={16} aria-hidden="true" />{c(error)}</p>
      {statusFailed && <button type="button" className="brain-secondary-button" onClick={() => void load()}>{c('Try again')}</button>}
    </div>}

    {!status ? statusFailed ? null : <div className="brain-source-skeletons" aria-busy="true" aria-label={c('Loading')}><div className="brain-source-skeleton"><span /><div><i /><i /></div></div></div>
      : !status.bot_configured ? <div className="brain-telegram-card" role="status">
        <Send size={26} aria-hidden="true" />
        <div><strong>{c('The Telegram bot is not set up on this server yet.')}</strong>
          <p>{c('You can still add anything here: drop files anywhere on the page or paste a link.')}</p></div>
      </div>
      : status.linked ? <div className="brain-telegram-card is-linked" role="status">
        <CheckCircle2 size={28} aria-hidden="true" />
        <div>
          <strong>{c('Telegram is connected.')}</strong>
          <p>{status.telegram_username ? `@${status.telegram_username}` : c('Your Telegram account')}{status.linked_at ? ` · ${formatBrainDate(new Date(status.linked_at), language)}` : ''}</p>
          <p>{c('Forward anything to the bot and it appears in your inbox.')}{status.bot_username && <> <a href={`https://t.me/${status.bot_username}`} target="_blank" rel="noreferrer">@{status.bot_username}<ExternalLink size={14} aria-hidden="true" /></a></>}</p>
        </div>
        <button type="button" className="brain-secondary-button" disabled={busy} onClick={() => void unlink()}><Unlink size={16} aria-hidden="true" />{c('Disconnect')}</button>
      </div>
      : !code || expired ? <div className="brain-telegram-card">
        <Send size={26} aria-hidden="true" />
        <div><strong>{expired ? c('The code expired.') : c('Connect your Telegram in one step.')}</strong>
          <p>{c('You will get a one-time code. Send it to the bot or scan the QR code with your phone.')}</p></div>
        <button type="button" className="brain-primary-button" disabled={busy} onClick={() => void connect()}>
          {expired ? <RefreshCw size={17} aria-hidden="true" /> : <Send size={17} aria-hidden="true" />}{expired ? c('Get a new code') : c('Connect Telegram')}
        </button>
      </div>
      : <div className="brain-telegram-link">
        <div className={`brain-telegram-qr${qrFailed ? ' is-unavailable' : ''}`}>{qrFailed
          ? <p role="status">{c('QR code unavailable. Open the link below or send your code to the bot.')}</p>
          : qr ? <img src={qr} width={232} height={232} alt={c('QR code that opens the Fibonacci bot in Telegram')} onError={() => setQrFailed(true)} /> : <span aria-hidden="true" />}</div>
        <div className="brain-telegram-steps">
          <p className="brain-section-kicker">{c('Your code')}</p>
          <p className="brain-telegram-code" aria-label={code.code.split('').join(' ')}>{code.code.slice(0, 3)}<span aria-hidden="true"> </span>{code.code.slice(3)}</p>
          <p className="brain-telegram-expiry" role="timer" aria-live="off">{c('Expires in')} {countdown}</p>
          <ol>
            <li>{c('Scan the QR code, or open the bot:')} <a href={code.deep_link} target="_blank" rel="noreferrer">{qrFailed ? code.deep_link : `@${code.bot_username}`}<ExternalLink size={14} aria-hidden="true" /></a></li>
            <li>{c('Press Start, or send the code to the bot.')}</li>
            <li>{c('This page updates as soon as you are connected.')}</li>
          </ol>
        </div>
      </div>}
  </section>
}
