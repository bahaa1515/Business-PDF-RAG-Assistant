import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import EvaluationPage from './EvaluationPage'
import * as api from '../api/client'

vi.mock('../api/client', () => ({
  runEvaluation: vi.fn(),
  getLatestEvaluation: vi.fn(),
  judgeEvaluation: vi.fn(),
  getErrorMessage: vi.fn((error) => error.message)
}))

describe('EvaluationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getLatestEvaluation.mockResolvedValue({ data: { data: null } })
  })

  it('runs a labeled evaluation and renders quality metrics', async () => {
    api.runEvaluation.mockResolvedValue({
      data: {
        data: {
          answer_correctness: 1,
          semantic_answer_correctness: 0.95,
          faithfulness: 0.9,
          context_relevance: 0.8,
          source_hit_rate: 1,
          refusal_accuracy: 1,
          average_latency: 0.2,
          total_questions: 2,
          answerable_questions: 1,
          unanswerable_questions: 1,
          prompt_variant: 'grounded_complete',
          benchmark_split: 'known',
          retrieval_profile: 'auto',
          answer_verification: false,
          llm_model: 'gpt-4o',
          embedding_model: 'text-embedding-3-large',
          index_result: { reindexed: false },
          results: [{
            question: 'Refund window?',
            question_type: 'answerable',
            reference_answer: '30 days',
            expected_source: 'policy.pdf',
            expected_page: 1,
            expected_locator: null,
            retrieved_sources: [{ filename: 'policy.pdf', page: 1, locator_label: 'Page 1' }],
            source_hit: true,
            correctly_refused: null,
            answer_correctness: 1,
            semantic_answer_correctness: 0.95,
            semantic_verdict: 'correct',
            semantic_explanation: 'Same meaning.',
            prompt_variant: 'grounded_complete',
            retrieval_profile: 'auto',
            resolved_retrieval_profile: 'auto_focused',
            answer_verification: false,
            top_k: 5,
            retrieval_method: 'hybrid',
            reranker: 'none',
            faithfulness: 0.9,
            context_relevance: 0.8,
            correctness_explanation: 'Matched the reference.',
            latency: 0.2,
            generated_answer: '30 days'
          }]
        }
      }
    })
    const { container } = render(<EvaluationPage />)
    const file = new File(['question,reference_answer'], 'evaluation.csv', { type: 'text/csv' })
    fireEvent.change(container.querySelector('input[type="file"]'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Run Evaluation' }))

    await waitFor(() => expect(screen.getByText('Same meaning.')).toBeInTheDocument())
    expect(screen.getByText('Retrieval Accuracy')).toBeInTheDocument()
    expect(screen.getByText('Semantic Correctness')).toBeInTheDocument()
    expect(screen.getByText('policy.pdf (Page 1)')).toBeInTheDocument()
    expect(screen.getByText('Same meaning.')).toBeInTheDocument()
    expect(screen.getAllByText('100.0%').length).toBeGreaterThan(0)
    expect(api.runEvaluation).toHaveBeenCalledOnce()
    expect(api.runEvaluation.mock.calls[0][1].chunking_strategy).toBe('structure')
    expect(api.runEvaluation.mock.calls[0][1].chunk_overlap).toBe(150)
    expect(api.runEvaluation.mock.calls[0][1].retrieval_method).toBe('hybrid')
    expect(api.runEvaluation.mock.calls[0][1].prompt_variant).toBe('grounded_complete')
    expect(api.runEvaluation.mock.calls[0][1].retrieval_profile).toBe('auto')
    expect(api.runEvaluation.mock.calls[0][1].answer_verification).toBe(false)
    expect(api.runEvaluation.mock.calls[0][1].benchmark_split).toBe('known')
    expect(api.runEvaluation.mock.calls[0][1].semantic_judge).toBe(false)
  })

  it('loads the latest saved evaluation without rerunning', async () => {
    api.getLatestEvaluation.mockResolvedValue({
      data: {
        data: {
          answer_correctness: 0.75,
          semantic_answer_correctness: 0.9,
          faithfulness: 0.8,
          context_relevance: 0.7,
          source_hit_rate: 0.9,
          refusal_accuracy: 1,
          average_latency: 0.3,
          total_questions: 1,
          answerable_questions: 1,
          unanswerable_questions: 0,
          prompt_variant: 'policy_procedure',
          benchmark_split: 'holdout',
          retrieval_profile: 'auto',
          answer_verification: true,
          llm_model: 'gpt-4o',
          embedding_model: 'text-embedding-3-large',
          results: [{
            question: 'Support scope?',
            question_type: 'answerable',
            reference_answer: 'GitLab customers',
            expected_source: 'support.pdf',
            expected_page: 1,
            expected_locator: null,
            retrieved_sources: [{ filename: 'support.pdf', page: 1 }],
            source_hit: true,
            correctly_refused: null,
            answer_correctness: 0.75,
            semantic_answer_correctness: 0.9,
            semantic_verdict: 'correct',
            semantic_explanation: 'Matches the reference meaning.',
            prompt_variant: 'policy_procedure',
            retrieval_profile: 'auto',
            resolved_retrieval_profile: 'auto_policy',
            answer_verification: true,
            top_k: 8,
            retrieval_method: 'hybrid',
            reranker: 'none',
            faithfulness: 0.8,
            context_relevance: 0.7,
            correctness_explanation: 'Partially matched.',
            latency: 0.3,
            generated_answer: 'GitLab customers'
          }]
        }
      }
    })

    render(<EvaluationPage />)

    expect(await screen.findByText('Loaded latest saved evaluation run.')).toBeInTheDocument()
    expect(screen.getByText('Matches the reference meaning.')).toBeInTheDocument()
    expect(api.runEvaluation).not.toHaveBeenCalled()
  })
})
