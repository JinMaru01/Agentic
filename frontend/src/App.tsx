import {
  BranchesOutlined,
} from '@ant-design/icons'
import { ConfigProvider, Layout, Spin, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { agentsApi, sessionsApi } from './api/client'
import ChatWindow from './components/ChatWindow'
import SessionSidebar from './components/SessionSidebar'
import type { AgentInfo, ChatMessage, SessionInfo } from './types'

const { Sider, Content, Header } = Layout

export default function App() {
  const [agents,          setAgents]          = useState<AgentInfo[]>([])
  const [sessions,        setSessions]        = useState<SessionInfo[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [activeMessages,  setActiveMessages]  = useState<ChatMessage[]>([])
  const [loadingInit,     setLoadingInit]     = useState(true)
  const [loadingSession,  setLoadingSession]  = useState(false)

  const [messageApi, contextHolder] = message.useMessage()

  // Load agents once
  useEffect(() => {
    agentsApi.list()
      .then(setAgents)
      .catch(() => messageApi.error('Failed to load agents'))
      .finally(() => setLoadingInit(false))
  }, [])

  async function refreshSessions() {
    const list = await sessionsApi.list()
    setSessions(list)
    return list
  }

  async function handleNewSession() {
    setLoadingSession(true)
    try {
      const { session_id } = await sessionsApi.create()
      await refreshSessions()
      setActiveSessionId(session_id)
      setActiveMessages([])
    } catch {
      messageApi.error('Failed to create session')
    } finally {
      setLoadingSession(false)
    }
  }

  async function handleSelectSession(id: string) {
    if (id === activeSessionId) return
    try {
      const { messages } = await sessionsApi.history(id)
      setActiveSessionId(id)
      setActiveMessages(messages)
    } catch {
      messageApi.error('Failed to load session history')
    }
  }

  async function handleDeleteSession(id: string) {
    try {
      await sessionsApi.delete(id)
      if (id === activeSessionId) {
        setActiveSessionId(null)
        setActiveMessages([])
      }
      await refreshSessions()
      messageApi.success('Session deleted')
    } catch {
      messageApi.error('Failed to delete session')
    }
  }

  if (loadingInit) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Spin size="large" tip="Connecting to agents…" />
      </div>
    )
  }

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#4f46e5',
          borderRadius: 8,
        },
      }}
    >
      {contextHolder}
      <Layout style={{ height: '100vh', overflow: 'hidden' }}>
        {/* Top navbar */}
        <Header
          style={{
            background:   '#fff',
            borderBottom: '1px solid #e5e7eb',
            padding:      '0 24px',
            display:      'flex',
            alignItems:   'center',
            gap:          12,
            boxShadow:    '0 1px 4px rgba(0,0,0,0.06)',
            zIndex:       10,
          }}
        >
          <BranchesOutlined style={{ fontSize: 22, color: '#4f46e5' }} />
          <Typography.Title level={4} style={{ margin: 0, color: '#1e1b4b' }}>
            Multi-Agent POC
          </Typography.Title>
          <Typography.Text type="secondary" style={{ marginLeft: 8, fontSize: 13 }}>
            Calculator · Mall Assistant · Auto Routing
          </Typography.Text>
        </Header>

        <Layout style={{ overflow: 'hidden' }}>
          {/* Session sidebar */}
          <Sider
            width={240}
            style={{
              background:   '#fff',
              borderRight:  '1px solid #e5e7eb',
              overflow:     'hidden',
              display:      'flex',
              flexDirection: 'column',
            }}
          >
            <SessionSidebar
              sessions={sessions}
              activeSessionId={activeSessionId}
              onNewSession={handleNewSession}
              onSelectSession={handleSelectSession}
              onDeleteSession={handleDeleteSession}
              loading={loadingSession}
            />
          </Sider>

          {/* Main content */}
          <Content style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            {activeSessionId ? (
              <ChatWindow
                key={activeSessionId}
                sessionId={activeSessionId}
                agents={agents}
                initialMessages={activeMessages}
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center px-8">
                <BranchesOutlined style={{ fontSize: 56, color: '#c7d2fe', marginBottom: 16 }} />
                <Typography.Title level={3} style={{ color: '#4f46e5', marginBottom: 8 }}>
                  Welcome to Multi-Agent POC
                </Typography.Title>
                <Typography.Text type="secondary" style={{ maxWidth: 420, lineHeight: 1.7 }}>
                  Test your agents interactively. Create a new session, select an agent
                  (or let Auto decide), and start chatting. If the selected agent isn't
                  the best fit, you'll get a smart switch suggestion.
                </Typography.Text>

                <div className="flex gap-6 mt-10 flex-wrap justify-center">
                  {agents.map(agent => (
                    <div
                      key={agent.id}
                      className="flex flex-col items-center gap-2 p-4 rounded-xl border border-gray-100 bg-white"
                      style={{ minWidth: 130, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}
                    >
                      <div
                        className="text-2xl"
                        style={{
                          background: `${agent.color}18`,
                          borderRadius: '50%',
                          width: 48,
                          height: 48,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: agent.color,
                          fontSize: 22,
                        }}
                      >
                        {agent.icon === 'robot'      ? '🤖' :
                         agent.icon === 'calculator' ? '🧮' :
                         agent.icon === 'shopping'   ? '🛍️' : '🤖'}
                      </div>
                      <Typography.Text strong style={{ color: agent.color, fontSize: 13 }}>
                        {agent.name}
                      </Typography.Text>
                      <Typography.Text type="secondary" style={{ fontSize: 11, textAlign: 'center' }}>
                        {agent.description}
                      </Typography.Text>
                    </div>
                  ))}
                </div>

                <Typography.Text
                  className="mt-8 text-indigo-400 cursor-pointer hover:text-indigo-600"
                  onClick={handleNewSession}
                  style={{ fontSize: 14 }}
                >
                  → Click "New Chat" in the sidebar to get started
                </Typography.Text>
              </div>
            )}
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  )
}
