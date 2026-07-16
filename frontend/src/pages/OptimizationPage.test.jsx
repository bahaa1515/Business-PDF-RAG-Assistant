import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import OptimizationPage from './OptimizationPage'
import * as api from '../api/client'

vi.mock('../api/client', () => ({
  runOptimization: vi.fn(),
  getOptimizationJob: vi.fn(),
  cancelOptimizationJob: vi.fn(),
  applyBestConfiguration: vi.fn(),
  getErrorMessage: vi.fn((error) => error.message)
}))

const optimizationResult = {
  run_id: 7,
  active_configuration: { chunk_size: 800, chunk_overlap: 100, chunking_strategy: 'auto' },
  results: [{
    rank: 1,
    chunk_size: 400,
    chunk_overlap: 50,
    chunking_strategy: 'structure',
    top_k: 3,
    retrieval_method: 'hybrid',
    reranker: 'enabled',
    prompt_variant: 'grounded_complete',
    semantic_answer_correctness: 0.95,
    answer_correctness: 0.9,
    faithfulness: 0.8,
    context_relevance: 0.7,
    source_hit_rate: 1,
    refusal_accuracy: 1,
    average_latency: 0.2,
    total_questions: 2,
    answerable_questions: 1,
    unanswerable_questions: 1
  }]
}

describe('OptimizationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.runOptimization.mockResolvedValue({
      data: { job_id: 'job-1', total_configurations: 48 }
    })
    api.getOptimizationJob.mockResolvedValue({
      data: { data: { job_id: 'job-1', status: 'completed', result: optimizationResult } }
    })
    api.applyBestConfiguration.mockResolvedValue({
      data: { data: { chunk_size: 400, chunk_overlap: 50, chunking_strategy: 'structure' } }
    })
  })

  it('starts a background job, renders results, and applies the best configuration', async () => {
    const { container } = render(<OptimizationPage />)
    const file = new File(['question\nQ'], 'evaluation.csv', { type: 'text/csv' })
    fireEvent.change(container.querySelector('input[type="file"]'), { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText('Estimated RAG calls').nextSibling).not.toBeNull())
    fireEvent.click(screen.getByRole('button', { name: 'Run Optimization' }))

    await waitFor(
      () => expect(screen.getByRole('button', { name: 'Apply Best Configuration' })).toBeInTheDocument(),
      { timeout: 3000 }
    )
    expect(screen.getByText('hybrid')).toBeInTheDocument()
    expect(screen.getByText('structure')).toBeInTheDocument()
    expect(screen.getByText('grounded complete')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Apply Best Configuration' }))
    await waitFor(() => expect(api.applyBestConfiguration).toHaveBeenCalledWith(7))
  })
})
