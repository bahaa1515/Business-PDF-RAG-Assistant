import React, { useEffect, useState } from 'react'
import * as api from '../api/client'

const SECTIONS = [
  ['low_faithfulness', 'Low faithfulness'],
  ['bad_feedback', 'Bad feedback'],
  ['no_chunks', 'No retrieved chunks'],
  ['unanswerable_not_refused', 'Unanswerable not refused'],
  ['answerable_source_miss', 'Answerable source miss']
]

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [clearing, setClearing] = useState(false)

  const loadAnalytics = () => {
    setError('')
    api.getFailedQuestionAnalytics()
      .then((response) => setAnalytics(response.data.data))
      .catch((requestError) => setError(api.getErrorMessage(requestError)))
  }

  useEffect(() => {
    loadAnalytics()
  }, [])

  const clearHistory = async () => {
    const confirmed = window.confirm(
      'Clear failed-question analytics history? Documents, indexes, provider settings, and successful chat history will stay unchanged.'
    )
    if (!confirmed) return

    setClearing(true)
    setError('')
    setMessage('')
    try {
      const response = await api.clearFailedQuestionAnalytics()
      const totalDeleted = response.data.data?.total_deleted || 0
      setMessage(`Failed-question analytics cleared. Removed ${totalDeleted} record${totalDeleted === 1 ? '' : 's'}.`)
      await loadAnalytics()
    } catch (requestError) {
      setError(api.getErrorMessage(requestError, 'Failed to clear failed-question analytics.'))
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="p-8">
      <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Failed Question Analytics</h1>
          <p className="text-gray-600 mt-2">Use evaluation signals and user feedback to find the next RAG improvements.</p>
        </div>
        <button
          onClick={clearHistory}
          disabled={clearing || !analytics}
          className="btn-secondary disabled:opacity-50"
        >
          {clearing ? 'Clearing...' : 'Clear History'}
        </button>
      </div>
      {error && <div className="card mb-6 bg-red-50 text-red-700">{error}</div>}
      {message && <div className="card mb-6 bg-green-50 text-green-700">{message}</div>}
      {!analytics ? <div className="card">Loading analytics...</div> : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            {SECTIONS.map(([key, label]) => <div key={key} className="card"><p className="text-sm text-gray-600">{label}</p><p className="text-3xl font-semibold">{analytics[key]?.length || 0}</p></div>)}
          </div>
          {SECTIONS.map(([key, label]) => <section key={key} className="card p-6">
            <h2 className="text-xl font-semibold mb-4">{label}</h2>
            {!analytics[key]?.length ? <p className="text-sm text-gray-500">No issues in this category.</p> : (
              <div className="space-y-3">{analytics[key].map((item) => <div key={`${key}-${item.id}`} className="bg-gray-50 rounded-lg p-4 text-sm"><p className="font-semibold">{item.question}</p><p className="text-gray-700 mt-1">{item.answer}</p>{item.comment && <p className="text-red-700 mt-2">Feedback: {item.comment}</p>}</div>)}</div>
            )}
          </section>)}
        </div>
      )}
    </div>
  )
}
