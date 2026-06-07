import { SwapOutlined } from '@ant-design/icons'
import { Alert, Button } from 'antd'

interface Props {
  suggestedAgent: string
  reason: string
  onSwitch: (agentId: string) => void
  onDismiss: () => void
}

export default function SuggestionAlert({ suggestedAgent, reason, onSwitch, onDismiss }: Props) {
  const label = suggestedAgent.charAt(0).toUpperCase() + suggestedAgent.slice(1)

  return (
    <Alert
      type="warning"
      showIcon
      closable
      onClose={onDismiss}
      className="mb-3"
      message={
        <span>
          <strong>Suggestion:</strong> Switch to the{' '}
          <strong>{label}</strong> agent?
        </span>
      }
      description={reason}
      action={
        <Button
          size="small"
          type="primary"
          icon={<SwapOutlined />}
          onClick={() => onSwitch(suggestedAgent)}
          style={{ background: '#f59e0b', borderColor: '#f59e0b' }}
        >
          Switch to {label}
        </Button>
      }
    />
  )
}
