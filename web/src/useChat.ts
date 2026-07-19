// useChat — conversation state for the Chat section: threads, streaming, sampling
// settings, and engine lifecycle (build / download / load the Bonsai model).
//
// Threads live in localStorage rather than on the server: they are per-browser scratch
// history, they never need to survive a `git pull` on the box, and keeping them client-side
// means no new persistence surface in the API.
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ChatMessage, ChatTimings, LlmStatus, LlmSampling,
  getLlmStatus, llmInstall, llmDownload, llmStart, llmStop, streamChat,
} from './api'

export type Msg = {
  id: string
  role: 'user' | 'assistant'
  content: string
  reasoning?: string        // out-of-band thinking (llama.cpp's reasoning_content)
  timings?: ChatTimings | null
  error?: string
}
export type Thread = { id: string; title: string; created: number; messages: Msg[] }

const STORE = 'relief.chat.threads.v1'
const SETTINGS = 'relief.chat.settings.v1'
const MAX_THREADS = 40                    // bound the localStorage footprint
const uid = () => Math.random().toString(36).slice(2, 10)

/**
 * Split a thinking model's raw output into its reasoning trace and its actual answer.
 * Bonsai is a thinking model, so replies arrive as `<think>…</think>answer`. Mid-stream
 * the closing tag has not arrived yet — an unterminated block is treated as reasoning
 * still in progress, which is what makes the "Thinking…" panel live-update.
 */
export function splitThinking(raw: string): { thinking: string; answer: string } {
  if (!raw.includes('<think>')) return { thinking: '', answer: raw }
  let thinking = ''
  let answer = ''
  let rest = raw
  for (;;) {
    const open = rest.indexOf('<think>')
    if (open === -1) { answer += rest; break }
    answer += rest.slice(0, open)
    const after = rest.slice(open + 7)
    const close = after.indexOf('</think>')
    if (close === -1) { thinking += after; break }        // still streaming
    thinking += after.slice(0, close)
    rest = after.slice(close + 8)
  }
  return { thinking: thinking.trim(), answer: answer.trim() }
}

const load = <T,>(key: string, fallback: T): T => {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch { return fallback }               // corrupt/absent storage must never block boot
}

const titleFrom = (text: string) => {
  const t = text.trim().replace(/\s+/g, ' ')
  return t.length > 42 ? t.slice(0, 42).trimEnd() + '…' : t || 'New chat'
}

export function useChat() {
  const [threads, setThreads] = useState<Thread[]>(() => load<Thread[]>(STORE, []))
  const [threadId, setThreadId] = useState<string>(() => load<Thread[]>(STORE, [])[0]?.id || '')
  const [llm, setLlm] = useState<LlmStatus | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [err, setErr] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const stored = load<Partial<LlmSampling & { system_prompt: string }>>(SETTINGS, {})
  const [sampling, setSampling] = useState<LlmSampling>({
    temperature: stored.temperature ?? 0.7,
    top_p: stored.top_p ?? 0.95,
    top_k: stored.top_k ?? 20,
    max_tokens: stored.max_tokens ?? 2048,
  })
  const [systemPrompt, setSystemPrompt] = useState(stored.system_prompt ?? 'You are a helpful assistant')

  const abortRef = useRef<AbortController | null>(null)

  // ---- persistence ----
  useEffect(() => {
    try { localStorage.setItem(STORE, JSON.stringify(threads.slice(0, MAX_THREADS))) } catch { /* quota */ }
  }, [threads])
  useEffect(() => {
    try { localStorage.setItem(SETTINGS, JSON.stringify({ ...sampling, system_prompt: systemPrompt })) } catch { /* quota */ }
  }, [sampling, systemPrompt])

  // ---- engine status polling ----
  const refreshLlm = useCallback(() => { getLlmStatus().then(setLlm).catch(() => {}) }, [])
  useEffect(() => {
    refreshLlm()
    // 1.5 s while a build/download/load is in flight so the log feels live; 5 s at rest.
    const t = setInterval(refreshLlm, llm?.busy ? 1500 : 5000)
    return () => clearInterval(t)
  }, [refreshLlm, llm?.busy])

  const thread = threads.find((t) => t.id === threadId) || null
  const messages = thread?.messages || []

  const patchThread = useCallback((id: string, fn: (t: Thread) => Thread) => {
    setThreads((ts) => ts.map((t) => (t.id === id ? fn(t) : t)))
  }, [])

  const newThread = useCallback(() => {
    abortRef.current?.abort()
    const t: Thread = { id: uid(), title: 'New chat', created: Date.now(), messages: [] }
    setThreads((ts) => [t, ...ts].slice(0, MAX_THREADS))
    setThreadId(t.id)
    setErr('')
    return t.id
  }, [])

  const deleteThread = useCallback((id: string) => {
    setThreads((ts) => {
      const next = ts.filter((t) => t.id !== id)
      if (id === threadId) setThreadId(next[0]?.id || '')
      return next
    })
  }, [threadId])

  const stop = useCallback(() => { abortRef.current?.abort() }, [])

  /**
   * Send `history` (already the full turn list) and stream the reply into a new assistant
   * message. Shared by send() and regenerate() so both paths behave identically.
   */
  const run = useCallback(async (tid: string, history: Msg[]) => {
    const replyId = uid()
    patchThread(tid, (t) => ({ ...t, messages: [...history, { id: replyId, role: 'assistant', content: '' }] }))
    setStreaming(true)
    setErr('')
    const ac = new AbortController()
    abortRef.current = ac

    const wire: ChatMessage[] = [
      ...(systemPrompt.trim() ? [{ role: 'system' as const, content: systemPrompt.trim() }] : []),
      ...history.map((m) => ({ role: m.role, content: m.content })),
    ]
    // Buffer deltas and flush on a frame: a fast GPU emits tokens well above 60/s, and a
    // setState per token would re-render the whole thread that often.
    let content = ''
    let reasoning = ''
    let dirty = false
    let raf = 0
    const flush = () => {
      raf = 0
      if (!dirty) return
      dirty = false
      patchThread(tid, (t) => ({
        ...t,
        messages: t.messages.map((m) => (m.id === replyId ? { ...m, content, reasoning } : m)),
      }))
    }
    const schedule = () => { dirty = true; if (!raf) raf = requestAnimationFrame(flush) }

    try {
      const timings = await streamChat(wire, sampling, (d) => {
        if (d.content) content += d.content
        if (d.reasoning) reasoning += d.reasoning
        schedule()
      }, ac.signal)
      if (raf) cancelAnimationFrame(raf)
      patchThread(tid, (t) => ({
        ...t,
        messages: t.messages.map((m) => (m.id === replyId ? { ...m, content, reasoning, timings } : m)),
      }))
    } catch (e: any) {
      if (raf) cancelAnimationFrame(raf)
      const aborted = e?.name === 'AbortError'
      const message = aborted ? '' : e?.message || String(e)
      if (!aborted) setErr(message)
      patchThread(tid, (t) => ({
        ...t,
        messages: t.messages
          // an aborted reply with nothing streamed yet is noise — drop the empty bubble
          .filter((m) => !(m.id === replyId && aborted && !content))
          .map((m) => (m.id === replyId ? { ...m, content, reasoning, error: message || undefined } : m)),
      }))
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }, [patchThread, sampling, systemPrompt])

  const send = useCallback(async (text: string) => {
    const body = text.trim()
    if (!body || streaming) return
    let tid = threadId
    let history: Msg[] = messages
    if (!thread) {
      tid = uid()
      history = []
      setThreads((ts) => [{ id: tid, title: titleFrom(body), created: Date.now(), messages: [] }, ...ts].slice(0, MAX_THREADS))
      setThreadId(tid)
    } else if (!messages.length) {
      patchThread(tid, (t) => ({ ...t, title: titleFrom(body) }))
    }
    await run(tid, [...history, { id: uid(), role: 'user', content: body }])
  }, [streaming, threadId, thread, messages, patchThread, run])

  /** Re-answer the last user turn, discarding the reply that followed it. */
  const regenerate = useCallback(async () => {
    if (streaming || !thread) return
    const lastUser = [...thread.messages].reverse().findIndex((m) => m.role === 'user')
    if (lastUser === -1) return
    const cut = thread.messages.length - lastUser
    await run(thread.id, thread.messages.slice(0, cut))
  }, [streaming, thread, run])

  // ---- engine actions ----
  const install = useCallback(() => { llmInstall().then(refreshLlm).catch(() => {}) }, [refreshLlm])
  const download = useCallback((keys?: string[]) => { llmDownload(keys).then(refreshLlm).catch(() => {}) }, [refreshLlm])
  const loadModel = useCallback((key: string) => { llmStart(key).then(refreshLlm).catch(() => {}) }, [refreshLlm])
  const unload = useCallback(() => { llmStop().then(refreshLlm).catch(() => {}) }, [refreshLlm])

  const resetSampling = useCallback(() => {
    setSampling({ temperature: 0.7, top_p: 0.95, top_k: 20, max_tokens: 2048 })
    setSystemPrompt('You are a helpful assistant')
  }, [])

  return {
    threads, thread, threadId, messages, llm, streaming, err,
    sampling, setSampling, systemPrompt, setSystemPrompt, resetSampling,
    settingsOpen, setSettingsOpen, sidebarOpen, setSidebarOpen,
    setThreadId, newThread, deleteThread, send, stop, regenerate,
    install, download, loadModel, unload, refreshLlm,
  }
}

export type Chat = ReturnType<typeof useChat>
