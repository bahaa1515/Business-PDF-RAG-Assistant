import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import CSVFormatHelp from './CSVFormatHelp'

describe('CSVFormatHelp', () => {
  it('documents the reference answer format and downloads a sample', () => {
    const createObjectURL = vi.fn(() => 'blob:sample')
    const revokeObjectURL = vi.fn()
    URL.createObjectURL = createObjectURL
    URL.revokeObjectURL = revokeObjectURL
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    render(<CSVFormatHelp />)
    expect(screen.getByText(/five required columns/i)).toBeInTheDocument()
    expect(screen.getAllByText(/expected_locator/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/answerable rows require reference_answer/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Download sample CSV' }))

    expect(createObjectURL).toHaveBeenCalledOnce()
    expect(click).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:sample')
    click.mockRestore()
  })
})
