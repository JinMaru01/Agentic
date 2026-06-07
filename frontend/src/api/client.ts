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

export const chatApi = {
  send: (session_id: string, message: string, selected_agent: string): Promise<ChatResponse> =>
    http.post<ChatResponse>('/chat', { session_id, message, selected_agent }).then(r => r.data),
}
