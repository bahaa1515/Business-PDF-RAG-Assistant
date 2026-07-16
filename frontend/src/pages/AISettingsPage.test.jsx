import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AISettingsPage from './AISettingsPage'
import * as api from '../api/client'

vi.mock('../api/client', () => ({
  getProviderSettings: vi.fn(),
  updateProviderSettings: vi.fn(),
  getErrorMessage: vi.fn((error, fallback) => error.message || fallback)
}))

const settingsData = {
  provider_options: ['openai', 'gemini', 'anthropic', 'groq', 'custom', 'ollama'],
  service_provider_options: {
    llm: ['openai', 'gemini', 'anthropic', 'groq', 'custom', 'ollama'],
    embedding: ['openai', 'gemini', 'groq', 'custom', 'ollama']
  },
  provider_model_defaults: {
    llm: {
      openai: 'gpt-4o-mini',
      gemini: 'gemini-2.5-flash',
      anthropic: 'claude-sonnet-4-5',
      ollama: 'qwen2.5:7b-instruct'
    },
    embedding: {
      openai: 'text-embedding-3-small',
      gemini: 'gemini-embedding-001',
      ollama: 'nomic-embed-text'
    }
  },
  llm: {
    provider: 'openai',
    model: 'gpt-4o-mini',
    base_url: '',
    requires_api_key: true,
    api_key_set: true,
    api_key_display: '********',
    source: 'saved'
  },
  embedding: {
    provider: 'openai',
    model: 'text-embedding-3-small',
    base_url: '',
    requires_api_key: true,
    api_key_set: true,
    api_key_display: '********',
    source: 'saved'
  }
}

describe('AISettingsPage security behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getProviderSettings.mockResolvedValue({ data: { data: settingsData } })
    api.updateProviderSettings.mockResolvedValue({ data: { data: settingsData } })
  })

  it('keeps saved keys masked and clears newly typed keys after save', async () => {
    render(<AISettingsPage />)
    await waitFor(() => expect(screen.getAllByText('Key saved - saved')).toHaveLength(2))

    const keyInputs = screen.getAllByLabelText('API key')
    expect(keyInputs).toHaveLength(2)
    keyInputs.forEach((input) => {
      expect(input).toHaveAttribute('type', 'password')
      expect(input).toHaveAttribute('placeholder', '********')
    })
    expect(screen.queryByRole('button', { name: /show|reveal/i })).not.toBeInTheDocument()

    fireEvent.change(keyInputs[0], { target: { value: 'sk-front-secret' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Settings' }))

    await waitFor(() => expect(api.updateProviderSettings).toHaveBeenCalledOnce())
    expect(api.updateProviderSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        llm: expect.objectContaining({ api_key: 'sk-front-secret' })
      })
    )
    await waitFor(() => expect(screen.queryByDisplayValue('sk-front-secret')).not.toBeInTheDocument())
  })

  it('shows Gemini and Claude as first-class provider options', async () => {
    render(<AISettingsPage />)
    await waitFor(() => expect(screen.getAllByText('Key saved - saved')).toHaveLength(2))

    expect(screen.getAllByRole('option', { name: 'Google Gemini' }).length).toBeGreaterThan(0)
    expect(screen.getByRole('option', { name: 'Anthropic Claude' })).toBeInTheDocument()
  })

  it('sets provider-specific model defaults and reports reindex warnings', async () => {
    const reindexResponse = {
      ...settingsData,
      reindex_required: true,
      embedding: {
        ...settingsData.embedding,
        provider: 'gemini',
        model: 'gemini-embedding-001'
      }
    }
    api.updateProviderSettings.mockResolvedValueOnce({ data: { data: reindexResponse } })
    render(<AISettingsPage />)
    await waitFor(() => expect(screen.getAllByText('Key saved - saved')).toHaveLength(2))

    const providerSelects = screen.getAllByLabelText('Provider')
    fireEvent.change(providerSelects[1], { target: { value: 'gemini' } })

    expect(screen.getByDisplayValue('gemini-embedding-001')).toBeInTheDocument()
    expect(screen.getByText(/Gemini embeddings use Google's native embedding API/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Save Settings' }))

    await waitFor(() => {
      expect(screen.getByText(/documents were marked for re-indexing/i)).toBeInTheDocument()
    })
  })
})
