import {
  CalculatorOutlined,
  RobotOutlined,
  ShoppingOutlined,
  UserOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { Avatar, Tag } from 'antd'
import dayjs from 'dayjs'
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

function renderContent(text: string) {
  // Bold (**text**) and newlines → <br>
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }
    return part.split('\n').map((line, j, arr) => (
      <span key={`${i}-${j}`}>
        {line}
        {j < arr.length - 1 && <br />}
      </span>
    ))
  })
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
        <div className="flex flex-col items-end max-w-[72%]">
          <div
            className="px-4 py-2.5 rounded-2xl rounded-tr-sm text-white text-sm leading-relaxed"
            style={{ background: '#4f46e5' }}
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

  return (
    <div className="flex gap-2 mb-4">
      <Avatar
        icon={AGENT_ICON[agentId] ?? <RobotOutlined />}
        style={{ background: agentColor, flexShrink: 0 }}
      />
      <div className="flex flex-col max-w-[72%]">
        {message.agent_used && <AgentBadge agentId={message.agent_used} />}
        <div
          className="px-4 py-2.5 rounded-2xl rounded-tl-sm bg-white text-sm leading-relaxed text-gray-800 message-content"
          style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.08)', border: '1px solid #f3f4f6' }}
        >
          {renderContent(message.content)}
        </div>
        <span className="text-xs text-gray-400 mt-1 ml-1">{time}</span>
      </div>
    </div>
  )
}
