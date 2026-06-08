import axios from 'axios'
import type { AgentInfo, ChatMessage, ChatResponse, SessionInfo } from '../types'

const http = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

export const agentsApi = {
  list: (): Promise<AgentInfo[]> =>
    http.get<AgentInfo[]>('/agents').then(r => r.data),
}

export const sessionsApi = {
  create: (): Promise<{ session_id: string }> =>
    http.post<{ session_id: string }>('/sessions').then(r => r.data),

  list: (): Promise<SessionInfo[]> =>
    http.get<SessionInfo[]>('/sessions').then(r => r.data),

  delete: (id: string): Promise<void> =>
    http.delete(`/sessions/${id}`).then(() => undefined),

  history: (id: string): Promise<{ session_id: string; messages: ChatMessage[] }> =>
    http.get(`/sessions/${id}/history`).then(r => r.data),
}

export interface StreamCallbacks {
  onToken:   (token: string) => void
  onStatus:  (status: string) => void
  onReplace: (text: string) => void
  onDone:    (meta: { agent_used: string; suggested_agent?: string | null; suggestion_reason?: string | null }) => void
  onError:   (err: string) => void
}

export const chatApi = {
  send: (session_id: string, message: string, selected_agent: string): Promise<ChatResponse> =>
    http.post<ChatResponse>('/chat', { session_id, message, selected_agent }).then(r => r.data),

  stream(
    session_id: string,
    message: string,
    selected_agent: string,
    callbacks: StreamCallbacks,
  ): AbortController {
    const controller = new AbortController()

    fetch('/api/chat/stream', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ session_id, message, selected_agent }),
      signal:  controller.signal,
    })
      .then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          callbacks.onError((err as { detail?: string }).detail ?? res.statusText)
          return
        }

        const reader  = res.body!.getReader()
        const decoder = new TextDecoder()
        let   buffer  = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const data = JSON.parse(line.slice(6)) as Record<string, unknown>
              if (typeof data.token === 'string') {
                callbacks.onToken(data.token)
              } else if (typeof data.status === 'string') {
                callbacks.onStatus(data.status)
              } else if (typeof data.replace === 'string') {
                callbacks.onReplace(data.replace)
              } else if (data.done) {
                callbacks.onDone(data as Parameters<StreamCallbacks['onDone']>[0])
              } else if (typeof data.error === 'string') {
                callbacks.onError(data.error)
              }
            } catch { /* ignore malformed SSE lines */ }
          }
        }
      })
      .catch(err => {
        if ((err as Error).name !== 'AbortError') callbacks.onError(String(err))
      })

    return controller
  },
}
