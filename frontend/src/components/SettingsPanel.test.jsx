import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import SettingsPanel from './SettingsPanel'

describe('SettingsPanel', () => {
  it('exposes hybrid retrieval and reranking controls', () => {
    const onSettingsChange = vi.fn()
    render(
      <SettingsPanel
        settings={{ top_k: 5, retrieval_method: 'similarity', reranker: 'none', retrieval_profile: 'manual', answer_verification: false, show_debug: false }}
        onSettingsChange={onSettingsChange}
      />
    )

    expect(screen.getByRole('option', { name: 'Hybrid vector + keyword' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Auto by question type' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Enabled' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Reranker'), { target: { value: 'enabled' } })
    expect(onSettingsChange).toHaveBeenCalledWith(expect.objectContaining({ reranker: 'enabled' }))
    fireEvent.click(screen.getByLabelText('Verify grounded answer'))
    expect(onSettingsChange).toHaveBeenCalledWith(expect.objectContaining({ answer_verification: true }))
  })
})
