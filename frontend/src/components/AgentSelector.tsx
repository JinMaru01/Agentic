import {
  CalculatorOutlined,
  RobotOutlined,
  ShoppingOutlined,
} from '@ant-design/icons'
import { Badge, Card, Tag, Tooltip } from 'antd'
import type { AgentInfo } from '../types'

const ICON_MAP: Record<string, React.ReactNode> = {
  robot:      <RobotOutlined style={{ fontSize: 28 }} />,
  calculator: <CalculatorOutlined style={{ fontSize: 28 }} />,
  shopping:   <ShoppingOutlined style={{ fontSize: 28 }} />,
}

interface Props {
  agents: AgentInfo[]
  selected: string
  onSelect: (id: string) => void
  disabled?: boolean
}

export default function AgentSelector({ agents, selected, onSelect, disabled }: Props) {
  return (
    <div className="flex gap-3 flex-wrap">
      {agents.map(agent => {
        const isSelected = selected === agent.id
        return (
          <Tooltip
            key={agent.id}
            title={
              <div>
                <div className="font-semibold mb-1">{agent.name}</div>
                <div className="text-xs mb-2 opacity-90">{agent.description}</div>
                <div className="flex flex-wrap gap-1">
                  {agent.capabilities.map(c => (
                    <Tag key={c} color="blue" style={{ fontSize: 11, margin: 0 }}>{c}</Tag>
                  ))}
                </div>
              </div>
            }
            placement="bottom"
          >
            <Card
              onClick={() => !disabled && onSelect(agent.id)}
              style={{
                cursor:      disabled ? 'not-allowed' : 'pointer',
                borderColor: isSelected ? agent.color : '#e5e7eb',
                borderWidth: isSelected ? 2 : 1,
                background:  isSelected ? `${agent.color}12` : '#fff',
                minWidth:    130,
                transition:  'all 0.2s',
                opacity:     disabled ? 0.6 : 1,
                boxShadow:   isSelected ? `0 0 0 2px ${agent.color}40` : undefined,
              }}
              bodyStyle={{ padding: '12px 16px' }}
            >
              <div className="flex flex-col items-center gap-1">
                <span style={{ color: isSelected ? agent.color : '#6b7280' }}>
                  {ICON_MAP[agent.icon] ?? <RobotOutlined style={{ fontSize: 28 }} />}
                </span>
                <span
                  className="text-sm font-medium text-center"
                  style={{ color: isSelected ? agent.color : '#374151' }}
                >
                  {agent.name}
                </span>
                {isSelected && (
                  <Badge
                    count="Active"
                    style={{ backgroundColor: agent.color, fontSize: 10, height: 16, lineHeight: '16px' }}
                  />
                )}
              </div>
            </Card>
          </Tooltip>
        )
      })}
    </div>
  )
}
