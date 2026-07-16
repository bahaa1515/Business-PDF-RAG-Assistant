import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ChatPage from './ChatPage'
import * as api from '../api/client'

vi.mock('../contexts/RoleContext', () => ({
  useRole: () => ({ role: 'user' })
}))

vi.mock('../api/client', () => ({
  getChatHistory: vi.fn(),
  chat: vi.fn(),
  submitFeedback: vi.fn(),
  getErrorMessage: vi.fn((error) => error.message)
}))

describe('ChatPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getChatHistory.mockResolvedValue({ data: { history: [] } })
  })

  it('asks a question using user defaults and stores feedback', async () => {
    api.chat.mockResolvedValue({
      data: {
        data: {
          chat_id: 10,
          answer: 'Refunds are available for 30 days.',
          sources: [{ filename: 'policy.pdf', page: 1 }],
          latency_seconds: 0.1,
          settings_used: { top_k: 5, retrieval_method: 'hybrid', reranker: 'none', retrieval_profile: 'manual', answer_verification: false }
        }
      }
    })
    api.submitFeedback.mockResolvedValue({})
    render(<ChatPage />)
    const question = screen.getByPlaceholderText('Ask a question...')
    fireEvent.change(question, { target: { value: 'What is the refund window?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(screen.getByText('Refunds are available for 30 days.')).toBeInTheDocument())
    expect(api.chat).toHaveBeenCalledWith(
      'What is the refund window?', 5, 'hybrid', 'none', false, 'manual', false
    )
    fireEvent.click(screen.getByRole('button', { name: 'Helpful' }))
    await waitFor(() => expect(api.submitFeedback).toHaveBeenCalledWith(10, 'up', ''))
  })
})
