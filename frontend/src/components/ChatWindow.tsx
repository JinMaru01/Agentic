import { SendOutlined } from '@ant-design/icons'
import { Button, Empty, Input, Spin } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { chatApi } from '../api/client'
import type { AgentInfo, ChatMessage, ChatResponse } from '../types'
import AgentSelector from './AgentSelector'
import MessageBubble from './MessageBubble'
import SuggestionAlert from './SuggestionAlert'

interface Props {
  sessionId: string
  agents: AgentInfo[]
  initialMessages?: ChatMessage[]
}

interface Suggestion {
  agentId: string
  reason: string
}

export default function ChatWindow({ sessionId, agents, initialMessages = [] }: Props) {
  const [messages,       setMessages]       = useState<ChatMessage[]>(initialMessages)
  const [selectedAgent,  setSelectedAgent]  = useState('auto')
  const [inputValue,     setInputValue]     = useState('')
  const [loading,        setLoading]        = useState(false)
  const [suggestion,     setSuggestion]     = useState<Suggestion | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Reset when session switches
  useEffect(() => {
    setMessages(initialMessages)
    setSuggestion(null)
    setInputValue('')
  }, [sessionId])

  // Auto-scroll to newest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleSend() {
    const text = inputValue.trim()
    if (!text || loading) return

    const userMsg: ChatMessage = {
      role:      'user',
      content:   text,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    setInputValue('')
    setLoading(true)
    setSuggestion(null)

    try {
      const res: ChatResponse = await chatApi.send(sessionId, text, selectedAgent)

      const assistantMsg: ChatMessage = {
        role:       'assistant',
        content:    res.response,
        agent_used: res.agent_used,
        timestamp:  new Date().toISOString(),
      }
      setMessages(prev => [...prev, assistantMsg])

      if (res.suggested_agent && res.suggestion_reason) {
        setSuggestion({ agentId: res.suggested_agent, reason: res.suggestion_reason })
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail ?? String(err)
      const errMsg: ChatMessage = {
        role:       'assistant',
        content:    `Error: ${detail}`,
        agent_used: 'error',
        timestamp:  new Date().toISOString(),
      }
      setMessages(prev => [...prev, errMsg])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleSwitchAgent(agentId: string) {
    setSelectedAgent(agentId)
    setSuggestion(null)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Agent selector */}
      <div className="px-5 py-4 border-b border-gray-100 bg-white">
        <div className="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wide">
          Select Agent
        </div>
        <AgentSelector
          agents={agents}
          selected={selectedAgent}
          onSelect={id => { setSelectedAgent(id); setSuggestion(null) }}
          disabled={loading}
        />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 chat-scroll" style={{ background: '#f8fafc' }}>
        {messages.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <div className="text-center">
                <div className="text-gray-400 text-sm mb-1">No messages yet</div>
                <div className="text-gray-300 text-xs">
                  Select an agent above, then type your message
                </div>
              </div>
            }
            className="mt-16"
          />
        ) : (
          messages.map((msg, i) => <MessageBubble key={i} message={msg} />)
        )}

        {loading && (
          <div className="flex gap-2 mb-4">
            <div
              className="px-4 py-3 rounded-2xl rounded-tl-sm bg-white text-sm text-gray-400"
              style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.08)', border: '1px solid #f3f4f6' }}
            >
              <Spin size="small" /> Thinking…
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Suggestion alert */}
      {suggestion && (
        <div className="px-5 pt-3">
          <SuggestionAlert
            suggestedAgent={suggestion.agentId}
            reason={suggestion.reason}
            onSwitch={handleSwitchAgent}
            onDismiss={() => setSuggestion(null)}
          />
        </div>
      )}

      {/* Input */}
      <div
        className="px-5 py-4 border-t border-gray-100 bg-white"
        style={{ boxShadow: '0 -1px 4px rgba(0,0,0,0.04)' }}
      >
        <div className="flex gap-2 items-end">
          <Input.TextArea
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${agents.find(a => a.id === selectedAgent)?.name ?? 'agent'}… (Enter to send, Shift+Enter for newline)`}
            autoSize={{ minRows: 1, maxRows: 5 }}
            disabled={loading}
            style={{ borderRadius: 12, resize: 'none' }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            disabled={!inputValue.trim()}
            style={{
              background:  '#4f46e5',
              borderColor: '#4f46e5',
              borderRadius: 10,
              height: 40,
              width:  40,
              flexShrink: 0,
            }}
          />
        </div>
        <div className="text-xs text-gray-400 mt-1.5 text-right">
          Session: {sessionId.slice(0, 8)}…
        </div>
      </div>
    </div>
  )
}
