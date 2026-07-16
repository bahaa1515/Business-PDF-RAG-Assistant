import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import UploadPanel from './UploadPanel'

describe('UploadPanel', () => {
  it('selects business documents and uploads them', async () => {
    const onUpload = vi.fn().mockResolvedValue()
    const { container } = render(<UploadPanel onUpload={onUpload} />)
    const input = container.querySelector('input[type="file"]')
    const file = new File(['# Policy'], 'policy.md', { type: 'text/markdown' })

    expect(input.getAttribute('accept')).toContain('.zip')
    expect(screen.getByText('Select business documents')).toBeInTheDocument()
    fireEvent.change(input, { target: { files: [file] } })
    expect(screen.getByText(/1 file\(s\) selected/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }))
    await waitFor(() => expect(onUpload).toHaveBeenCalledWith([file]))
    expect(screen.queryByText(/1 file\(s\) selected/i)).not.toBeInTheDocument()
  })
})
