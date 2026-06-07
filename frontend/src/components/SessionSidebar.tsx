import {
  DeleteOutlined,
  MessageOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import { Button, Empty, List, Popconfirm, Typography } from 'antd'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import type { SessionInfo } from '../types'

dayjs.extend(relativeTime)

interface Props {
  sessions: SessionInfo[]
  activeSessionId: string | null
  onNewSession: () => void
  onSelectSession: (id: string) => void
  onDeleteSession: (id: string) => void
  loading?: boolean
}

export default function SessionSidebar({
  sessions,
  activeSessionId,
  onNewSession,
  onSelectSession,
  onDeleteSession,
  loading,
}: Props) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-gray-100">
        <Button
          type="primary"
          icon={<PlusOutlined />}
          block
          onClick={onNewSession}
          loading={loading}
          style={{ background: '#4f46e5', borderColor: '#4f46e5' }}
        >
          New Chat
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {sessions.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={<span className="text-gray-400 text-xs">No sessions yet</span>}
            className="mt-8"
          />
        ) : (
          <List
            dataSource={[...sessions].reverse()}
            renderItem={session => {
              const isActive = session.session_id === activeSessionId
              return (
                <List.Item
                  className="rounded-lg mb-1 cursor-pointer transition-colors"
                  style={{
                    background:  isActive ? '#eef2ff' : 'transparent',
                    border:      isActive ? '1px solid #c7d2fe' : '1px solid transparent',
                    padding:     '8px 10px',
                  }}
                  onClick={() => onSelectSession(session.session_id)}
                  actions={[
                    <Popconfirm
                      key="del"
                      title="Delete this session?"
                      onConfirm={e => {
                        e?.stopPropagation()
                        onDeleteSession(session.session_id)
                      }}
                      onCancel={e => e?.stopPropagation()}
                      okText="Delete"
                      okType="danger"
                    >
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={e => e.stopPropagation()}
                      />
                    </Popconfirm>,
                  ]}
                >
                  <List.Item.Meta
                    avatar={
                      <MessageOutlined
                        style={{ color: isActive ? '#4f46e5' : '#9ca3af', fontSize: 16, marginTop: 2 }}
                      />
                    }
                    title={
                      <Typography.Text
                        strong={isActive}
                        style={{ fontSize: 13, color: isActive ? '#4f46e5' : '#374151' }}
                        ellipsis
                      >
                        {session.session_id.slice(0, 8)}…
                      </Typography.Text>
                    }
                    description={
                      <div className="flex flex-col">
                        <span className="text-xs text-gray-400">
                          {session.message_count} message{session.message_count !== 1 ? 's' : ''}
                        </span>
                        <span className="text-xs text-gray-400">
                          {dayjs(session.last_active).fromNow()}
                        </span>
                      </div>
                    }
                  />
                </List.Item>
              )
            }}
          />
        )}
      </div>
    </div>
  )
}
