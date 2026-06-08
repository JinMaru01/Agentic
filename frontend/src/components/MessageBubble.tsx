import {
  CalculatorOutlined,
  RobotOutlined,
  ShoppingOutlined,
  UserOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { Avatar, Tag } from 'antd'
import dayjs from 'dayjs'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage } from '../types'

const AGENT_COLOR: Record<string, string> = {
  auto:       '#6366f1',
  calculator: '#10b981',
  mall:       '#f59e0b',
  error:      '#ef4444',
}

const AGENT_ICON: Record<string, React.ReactNode> = {
  auto:       <RobotOutlined />,
  calculator: <CalculatorOutlined />,
  mall:       <ShoppingOutlined />,
  error:      <WarningOutlined />,
}

function AgentBadge({ agentId }: { agentId: string }) {
  const color = AGENT_COLOR[agentId] ?? '#6b7280'
  const icon  = AGENT_ICON[agentId] ?? <RobotOutlined />
  const label = agentId.charAt(0).toUpperCase() + agentId.slice(1)
  return (
    <Tag
      icon={icon}
      style={{ color, borderColor: `${color}40`, background: `${color}12`, marginBottom: 4, fontSize: 11 }}
    >
      {label}
    </Tag>
  )
}

function ThinkingDots() {
  return (
    <span className="thinking-dots">
      <span /><span /><span />
    </span>
  )
}

const mdComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  p:          ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
  ul:         ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
  ol:         ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
  li:         ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong:     ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
  em:         ({ children }) => <em className="italic">{children}</em>,
  h1:         ({ children }) => <h1 className="text-sm font-semibold mb-1 mt-2">{children}</h1>,
  h2:         ({ children }) => <h2 className="text-sm font-semibold mb-1 mt-2">{children}</h2>,
  h3:         ({ children }) => <h3 className="text-sm font-semibold mb-1 mt-2">{children}</h3>,
  code:       ({ children, className }) => {
    const isBlock = className?.includes('language-')
    return isBlock
      ? <code className="block bg-gray-100 rounded px-2 py-1.5 text-xs font-mono overflow-x-auto">{children}</code>
      : <code className="bg-gray-100 rounded px-1 py-0.5 text-xs font-mono text-indigo-700">{children}</code>
  },
  pre:        ({ children }) => <pre className="bg-gray-100 rounded-lg p-3 mb-2 overflow-x-auto text-xs">{children}</pre>,
  blockquote: ({ children }) => <blockquote className="border-l-2 border-gray-300 pl-3 text-gray-500 italic mb-2">{children}</blockquote>,
  a:          ({ children, href }) => <a href={href} target="_blank" rel="noreferrer" className="text-indigo-600 underline">{children}</a>,
}

interface Props {
  message: ChatMessage
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const time   = dayjs(message.timestamp).format('HH:mm')

  if (isUser) {
    return (
      <div className="flex justify-end gap-2 mb-4">
        <div className="flex flex-col items-end max-w-[65%]">
          <div
            className="px-4 py-2.5 rounded-2xl rounded-tr-sm text-white text-sm leading-relaxed"
            style={{ background: '#4f46e5', wordBreak: 'break-word', overflowWrap: 'anywhere' }}
          >
            {message.content}
          </div>
          <span className="text-xs text-gray-400 mt-1 mr-1">{time}</span>
        </div>
        <Avatar icon={<UserOutlined />} style={{ background: '#818cf8', flexShrink: 0 }} />
      </div>
    )
  }

  const agentId    = message.agent_used ?? 'auto'
  const agentColor = AGENT_COLOR[agentId] ?? '#6366f1'
  const isStreaming = message.streaming
  const hasContent  = message.content.length > 0

  return (
    <div className="flex gap-2 mb-4">
      <Avatar
        icon={AGENT_ICON[agentId] ?? <RobotOutlined />}
        style={{ background: agentColor, flexShrink: 0 }}
      />
      <div className="flex flex-col max-w-[65%]">
        {message.agent_used && <AgentBadge agentId={message.agent_used} />}
        <div
          className="px-4 py-2.5 rounded-2xl rounded-tl-sm bg-white text-sm text-gray-800 message-content"
          style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.08)', border: '1px solid #f3f4f6' }}
        >
          {isStreaming && !hasContent ? (
            <span className="flex items-center gap-2 text-gray-400 text-xs">
              <ThinkingDots />
              <span className="italic">{message.status ?? 'Routing…'}</span>
            </span>
          ) : (
            <>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                {message.content}
              </ReactMarkdown>
              {isStreaming && <span className="cursor-blink">▌</span>}
            </>
          )}
        </div>
        <span className="text-xs text-gray-400 mt-1 ml-1">{time}</span>
      </div>
    </div>
  )
}
