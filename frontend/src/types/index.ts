export interface AgentInfo {
  id: string
  name: string
  description: string
  capabilities: string[]
  icon: string
  color: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  agent_used?: string
  timestamp: string
}

export interface ChatResponse {
  session_id: string
  response: string
  agent_used: string
  suggested_agent?: string
  suggestion_reason?: string
  error?: string
}

export interface SessionInfo {
  session_id: string
  created_at: string
  last_active: string
  message_count: number
}
