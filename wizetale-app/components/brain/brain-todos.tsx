'use client'

import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Trash2 } from 'lucide-react'
import type { BrainApi } from '@/lib/brain-api'
import type { BrainTodo } from '@/lib/brain-types'
import { useCopy } from '@/hooks/use-copy'
import { withUiTimeout } from './brain-ui-state'

export function BrainTodos({ api, refreshVersion }: { api: BrainApi; refreshVersion: number }) {
  const c = useCopy()
  const [todos, setTodos] = useState<BrainTodo[]>([])
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const [adding, setAdding] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<Set<string>>(new Set())
  const pending = useRef(new Map<string, boolean>())
  const deleting = useRef(new Set<string>())
  const request = useRef(0)

  const reload = useCallback(async () => {
    const version = ++request.current
    try {
      const items = await withUiTimeout(api.todos())
      if (request.current !== version) return
      // Preserve optimistic checkboxes across a concurrent Telegram refresh.
      setTodos(items.filter(item => !deleting.current.has(item.id)).map(item =>
        pending.current.has(item.id) ? { ...item, done: pending.current.get(item.id)! } : item))
      setLoadError(false)
    } catch {
      if (request.current === version) setLoadError(true)
    } finally {
      if (request.current === version) setLoading(false)
    }
  }, [api])

  useEffect(() => {
    void reload()
    return () => { request.current += 1 }
  }, [reload, refreshVersion])

  function markBusy(id: string, value: boolean) {
    setBusy(current => { const next = new Set(current); if (value) next.add(id); else next.delete(id); return next })
  }

  async function toggle(todo: BrainTodo) {
    if (pending.current.has(todo.id) || deleting.current.has(todo.id)) return
    pending.current.set(todo.id, !todo.done)
    markBusy(todo.id, true)
    setError(null)
    setTodos(current => current.map(item => item.id === todo.id ? { ...item, done: !todo.done } : item))
    try {
      const saved = await withUiTimeout(api.updateTodo(todo.id, { done: !todo.done }))
      setTodos(current => current.map(item => item.id === saved.id ? saved : item))
    } catch {
      setTodos(current => current.map(item => item.id === todo.id ? { ...item, done: todo.done } : item))
      setError('Could not save this to-do. Try again.')
    } finally {
      pending.current.delete(todo.id)
      markBusy(todo.id, false)
      void reload()
    }
  }

  async function remove(todo: BrainTodo) {
    if (pending.current.has(todo.id) || deleting.current.has(todo.id)) return
    deleting.current.add(todo.id)
    markBusy(todo.id, true)
    setError(null)
    try {
      await withUiTimeout(api.deleteTodo(todo.id))
      setTodos(current => current.filter(item => item.id !== todo.id))
    } catch {
      setError('Could not delete this to-do. Try again.')
    } finally {
      deleting.current.delete(todo.id)
      markBusy(todo.id, false)
      void reload()
    }
  }

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!title.trim() || adding) return
    setAdding(true)
    setError(null)
    try {
      const saved = await withUiTimeout(api.createTodo({ title: title.trim(), ...(due.trim() ? { due: due.trim() } : {}) }))
      setTodos(current => [saved, ...current.filter(item => item.id !== saved.id)])
      setTitle('')
      setDue('')
    } catch {
      setError('Could not save this to-do. Try again.')
    } finally {
      setAdding(false)
      void reload()
    }
  }

  const sorted = [...todos].sort((a, b) => Number(a.done) - Number(b.done))
  const count = todos.filter(item => !item.done).length
  return <section className="brain-todos" aria-labelledby="brain-todos-title">
    <header className="brain-section-row">
      <h2 id="brain-todos-title">{c('To do')}</h2>
      <span className="brain-todos-count" aria-live="polite">{c('{count} open').replace('{count}', String(count))}</span>
    </header>
    {loading && <p className="brain-todos-note" role="status">{c('Loading to-dos…')}</p>}
    {loadError && <div className="brain-todos-error" role="alert">{c('Could not load to-dos. Try again.')} <button type="button" className="brain-text-button" onClick={() => void reload()}>{c('Try again')}</button></div>}
    {!loading && !loadError && !todos.length && <p className="brain-todos-note">{c('Nothing to do. Send the bot a message like “read chapter 9 by Friday” and it lands here.')}</p>}
    <ul className="brain-todos-list">
      {sorted.map(todo => <li key={todo.id} className={todo.done ? 'is-done' : undefined}>
        <label className="brain-todo-label">
          <input type="checkbox" checked={todo.done} disabled={busy.has(todo.id)} onChange={() => void toggle(todo)} />
          <span className="brain-todo-content"><span className="brain-todo-title">{todo.title}</span>{todo.due && <small>{c('Due')}: {todo.due}</small>}</span>
        </label>
        {todo.source === 'telegram' && <span className="brain-todo-source">{c('Telegram')}</span>}
        <button type="button" className="brain-todo-delete" disabled={busy.has(todo.id)} aria-label={c('Delete to-do {title}').replace('{title}', todo.title)} onClick={() => void remove(todo)}><Trash2 size={16} aria-hidden="true" /></button>
      </li>)}
    </ul>
    <form className="brain-todos-form" onSubmit={add}>
      <input type="text" aria-label={c('Add a to-do')} placeholder={c('Add a to-do')} value={title} onChange={event => setTitle(event.target.value)} disabled={adding} required />
      <input type="text" className="brain-todo-due" aria-label={c('Due (optional)')} placeholder={c('Due')} value={due} onChange={event => setDue(event.target.value)} disabled={adding} />
      <button type="submit" className="brain-secondary-button" disabled={adding || !title.trim()}>{c(adding ? 'Adding…' : 'Add')}</button>
    </form>
    {error && <p className="brain-todos-error" role="alert">{c(error)}</p>}
  </section>
}
