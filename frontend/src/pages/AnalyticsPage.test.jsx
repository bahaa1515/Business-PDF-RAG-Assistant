import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AnalyticsPage from './AnalyticsPage'
import * as api from '../api/client'

vi.mock('../api/client', () => ({
  getFailedQuestionAnalytics: vi.fn(),
  clearFailedQuestionAnalytics: vi.fn(),
  getErrorMessage: vi.fn(() => 'Analytics unavailable')
}))

const emptyAnalytics = {
  low_faithfulness: [],
  bad_feedback: [],
  no_chunks: [],
  unanswerable_not_refused: [],
  answerable_source_miss: []
}

describe('AnalyticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders failed-question categories and records', async () => {
    api.getFailedQuestionAnalytics.mockResolvedValue({
      data: {
        data: {
          ...emptyAnalytics,
          bad_feedback: [{ id: 1, question: 'Refund?', answer: '90 days', comment: 'Wrong' }]
        }
      }
    })
    render(<AnalyticsPage />)
    await waitFor(() => expect(screen.getByText('Refund?')).toBeInTheDocument())
    expect(screen.getByText('Feedback: Wrong')).toBeInTheDocument()
    expect(screen.getAllByText('No issues in this category.')).toHaveLength(4)
  })

  it('shows a clean loading error', async () => {
    api.getFailedQuestionAnalytics.mockRejectedValue(new Error('network'))
    render(<AnalyticsPage />)
    await waitFor(() => expect(screen.getByText('Analytics unavailable')).toBeInTheDocument())
  })

  it('clears failed-question analytics after confirmation', async () => {
    api.getFailedQuestionAnalytics
      .mockResolvedValueOnce({
        data: {
          data: {
            ...emptyAnalytics,
            bad_feedback: [{ id: 1, question: 'Refund?', answer: '90 days', comment: 'Wrong' }]
          }
        }
      })
      .mockResolvedValueOnce({ data: { data: emptyAnalytics } })
    api.clearFailedQuestionAnalytics.mockResolvedValue({
      data: { data: { total_deleted: 1 } }
    })

    render(<AnalyticsPage />)
    await waitFor(() => expect(screen.getByText('Refund?')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Clear History' }))

    await waitFor(() => expect(api.clearFailedQuestionAnalytics).toHaveBeenCalledTimes(1))
    expect(window.confirm).toHaveBeenCalled()
    expect(await screen.findByText('Failed-question analytics cleared. Removed 1 record.')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('Refund?')).not.toBeInTheDocument())
  })
})
