import { SendOutlined } from '@ant-design/icons'
import { Button, Empty, Input, Spin } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { chatApi } from '../api/client'
import type { AgentInfo, ChatMessage } from '../types'
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
  const [messages,      setMessages]      = useState<ChatMessage[]>(initialMessages)
  const [selectedAgent, setSelectedAgent] = useState('auto')
  const [inputValue,    setInputValue]    = useState('')
  const [loading,       setLoading]       = useState(false)
  const [suggestion,    setSuggestion]    = useState<Suggestion | null>(null)
  const bottomRef    = useRef<HTMLDivElement>(null)
  const abortRef     = useRef<AbortController | null>(null)

  // Reset when session switches
  useEffect(() => {
    setMessages(initialMessages)
    setSuggestion(null)
    setInputValue('')
  }, [sessionId])

  // Auto-scroll on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  function handleSend() {
    const text = inputValue.trim()
    if (!text || loading) return

    // Abort any in-flight stream
    abortRef.current?.abort()

    setMessages(prev => [
      ...prev,
      { role: 'user', content: text, timestamp: new Date().toISOString() },
    ])
    setInputValue('')
    setLoading(true)
    setSuggestion(null)

    let firstToken = true

    abortRef.current = chatApi.stream(sessionId, text, selectedAgent, {
      onToken(token) {
        if (firstToken) {
          firstToken = false
          setLoading(false)
          // Add the streaming assistant message on first token
          setMessages(prev => [
            ...prev,
            { role: 'assistant', content: token, timestamp: new Date().toISOString() },
          ])
        } else {
          // Append subsequent tokens to the last message
          setMessages(prev => {
            const updated = [...prev]
            const last    = updated[updated.length - 1]
            if (last?.role === 'assistant') {
              updated[updated.length - 1] = { ...last, content: last.content + token }
            }
            return updated
          })
        }
      },

      onReplace(text) {
        // Swap the entire assistant message (e.g. raw-JSON was streamed, backend sends clean version)
        setMessages(prev => {
          const updated = [...prev]
          const last    = updated[updated.length - 1]
          if (last?.role === 'assistant') {
            updated[updated.length - 1] = { ...last, content: text }
          }
          return updated
        })
      },

      onDone(meta) {
        // Stamp agent_used onto the last message
        setMessages(prev => {
          const updated = [...prev]
          const last    = updated[updated.length - 1]
          if (last?.role === 'assistant') {
            updated[updated.length - 1] = { ...last, agent_used: meta.agent_used }
          }
          return updated
        })
        if (meta.suggested_agent && meta.suggestion_reason) {
          setSuggestion({ agentId: meta.suggested_agent, reason: meta.suggestion_reason })
        }
        setLoading(false)
      },

      onError(err) {
        const errMsg: ChatMessage = {
          role:       'assistant',
          content:    `Error: ${err}`,
          agent_used: 'error',
          timestamp:  new Date().toISOString(),
        }
        if (firstToken) {
          setMessages(prev => [...prev, errMsg])
        } else {
          setMessages(prev => {
            const updated = [...prev]
            if (updated[updated.length - 1]?.role === 'assistant') {
              updated[updated.length - 1] = errMsg
            }
            return updated
          })
        }
        setLoading(false)
      },
    })
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
      <div className="flex-1 overflow-y-auto px-5 py-4 chat-scroll chat-messages-bg">
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
            <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-white text-sm text-gray-400 chat-thinking-bubble">
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
      <div className="px-5 py-4 border-t border-gray-100 bg-white chat-input-bar">
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
              background:   '#4f46e5',
              borderColor:  '#4f46e5',
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
