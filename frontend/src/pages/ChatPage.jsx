import React, { useEffect, useState } from 'react'
import { useRole } from '../contexts/RoleContext'
import SettingsPanel from '../components/SettingsPanel'
import SourceCard from '../components/SourceCard'
import RetrievalDebugPanel from '../components/RetrievalDebugPanel'
import * as api from '../api/client'

const USER_DEFAULTS = {
  top_k: 5,
  retrieval_method: 'hybrid',
  reranker: 'none',
  retrieval_profile: 'manual',
  answer_verification: false,
  show_debug: false
}

export default function ChatPage() {
  const { role } = useRole()
  const isAdmin = role === 'admin'
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [settings, setSettings] = useState(USER_DEFAULTS)
  const [feedbackDrafts, setFeedbackDrafts] = useState({})

  const loadHistory = async () => {
    try {
      const response = await api.getChatHistory(50)
      setMessages(response.data.history || [])
    } catch (error) {
      console.error('Error loading chat history:', error)
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!question.trim()) return

    setLoading(true)
    const userMessage = question
    const activeSettings = isAdmin ? settings : USER_DEFAULTS
    setQuestion('')

    try {
      const response = await api.chat(
        userMessage,
        activeSettings.top_k,
        activeSettings.retrieval_method,
        activeSettings.reranker,
        activeSettings.show_debug,
        activeSettings.retrieval_profile,
        activeSettings.answer_verification
      )
      const data = response.data.data
      setMessages((current) => [...current, {
        id: data.chat_id,
        timestamp: new Date().toISOString(),
        question: userMessage,
        answer: data.answer,
        sources: data.sources,
        retrieved_chunks: data.retrieved_chunks,
        latency_seconds: data.latency_seconds,
        top_k: data.settings_used?.top_k,
        retrieval_method: data.settings_used?.retrieval_method,
        reranker: data.settings_used?.reranker,
        retrieval_profile: data.settings_used?.retrieval_profile,
        resolved_retrieval_profile: data.settings_used?.resolved_retrieval_profile,
        answer_verification: data.settings_used?.answer_verification
      }])
    } catch (error) {
      alert(api.getErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }

  const handleFeedback = async (message, rating) => {
    if (!message.id) return
    try {
      await api.submitFeedback(message.id, rating, feedbackDrafts[message.id] || '')
      setMessages((current) => current.map((item) => item.id === message.id ? { ...item, feedback: rating } : item))
    } catch (error) {
      alert(api.getErrorMessage(error, 'Could not save feedback.'))
    }
  }

  const handleClearHistory = async () => {
    if (!confirm('Clear chat history?')) return
    try {
      await api.clearChatHistory()
      setMessages([])
    } catch (error) {
      alert(api.getErrorMessage(error))
    }
  }

  useEffect(() => {
    loadHistory()
  }, [])

  return (
    <div className="p-4 sm:p-8">
      <h1 className="text-3xl font-bold mb-8">Chat</h1>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {isAdmin && (
          <div className="lg:col-span-1">
            <SettingsPanel settings={settings} onSettingsChange={setSettings} mode="chat" />
            <button onClick={handleClearHistory} className="btn-secondary w-full mt-4">Clear History</button>
          </div>
        )}

        <div className={`${isAdmin ? 'lg:col-span-3' : 'lg:col-span-4'} flex flex-col h-[calc(100vh-120px)]`}>
          <div className="flex-1 overflow-y-auto mb-6 space-y-4">
            {messages.length === 0 ? (
              <div className="text-center text-gray-600 py-12">No messages yet. Ask a question to get started.</div>
            ) : messages.map((message) => (
              <div key={message.id} className="space-y-2">
                <div className="flex justify-end">
                  <div className="card max-w-md bg-blue-50 border-l-4 border-l-blue-500">
                    <p className="text-sm font-medium text-blue-700">{message.question}</p>
                  </div>
                </div>
                <div className="card max-w-2xl">
                  <p className="text-gray-800 mb-3">{message.answer}</p>
                  {message.sources?.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <p className="text-sm font-semibold mb-2">Sources</p>
                      {message.sources.map((source, index) => <SourceCard key={index} source={source} rank={source.rank} />)}
                    </div>
                  )}
                  {isAdmin && message.retrieved_chunks && <RetrievalDebugPanel chunks={message.retrieved_chunks} />}
                  <p className="text-xs text-gray-500 mt-3">
                    {message.latency_seconds?.toFixed(2)}s
                    {isAdmin && message.top_k ? ` | Top K ${message.top_k} | ${message.retrieval_method} | reranker ${message.reranker || 'none'} | ${message.resolved_retrieval_profile || message.retrieval_profile || 'manual'}${message.answer_verification ? ' | verified' : ''}` : ''}
                  </p>
                  <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap gap-2 items-center">
                    <button type="button" onClick={() => handleFeedback(message, 'up')} className={`btn-secondary text-sm ${message.feedback === 'up' ? 'ring-2 ring-green-500' : ''}`}>Helpful</button>
                    <button type="button" onClick={() => handleFeedback(message, 'down')} className={`btn-secondary text-sm ${message.feedback === 'down' ? 'ring-2 ring-red-500' : ''}`}>Not helpful</button>
                    <input
                      type="text"
                      value={feedbackDrafts[message.id] || ''}
                      onChange={(event) => setFeedbackDrafts((current) => ({ ...current, [message.id]: event.target.value }))}
                      placeholder="Optional feedback comment"
                      className="input-field flex-1 min-w-56 text-sm"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="card flex flex-col sm:flex-row gap-2">
            <input type="text" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question..." disabled={loading} className="input-field flex-1 min-w-0" />
            <button type="submit" disabled={loading || !question.trim()} className="btn-primary w-full sm:w-auto disabled:opacity-50">
              {loading ? 'Thinking...' : 'Send'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
