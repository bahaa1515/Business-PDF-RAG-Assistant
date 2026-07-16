import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DocumentsPage from './DocumentsPage'
import * as api from '../api/client'

vi.mock('../api/client', () => ({
  getDocuments: vi.fn(),
  getIndexStatus: vi.fn(),
  updateIndexSettings: vi.fn(),
  getDocumentPreview: vi.fn(),
  uploadDocuments: vi.fn(),
  deleteDocument: vi.fn(),
  reindexDocuments: vi.fn(),
  resetIndex: vi.fn(),
  getErrorMessage: vi.fn((error) => error.message)
}))

const document = {
  id: 1,
  filename: 'policy.pdf',
  document_type: 'pdf',
  page_count: 2,
  content_unit_count: 2,
  chunk_count: 4,
  chunking_strategy: 'auto',
  status: 'indexed',
  upload_time: '2026-01-01T00:00:00Z'
}

describe('DocumentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.confirm = vi.fn(() => true)
    api.getDocuments.mockResolvedValue({ data: { documents: [document] } })
    api.getIndexStatus.mockResolvedValue({
      data: {
        data: {
          ready: true,
          configuration: {
            chunk_size: 800,
            chunk_overlap: 100,
            chunking_strategy: 'auto'
          }
        }
      }
    })
    api.getDocumentPreview.mockResolvedValue({
      data: { data: { first_text_preview: 'Refund policy text', chunk_previews: [{ page: 1, locator_label: 'Page 1', chunk_id: 1, preview: 'Refunds in 30 days' }] } }
    })
    api.updateIndexSettings.mockResolvedValue({ data: { data: { changed: false, reindex_required: false, stale_documents: 0 } } })
    api.reindexDocuments.mockResolvedValue({ data: { result: { total_chunks: 4 } } })
    api.resetIndex.mockResolvedValue({})
    api.deleteDocument.mockResolvedValue({})
    api.uploadDocuments.mockResolvedValue({ data: { total: 1, total_uploaded: 1, total_rejected: 0, rejected_files: [] } })
  })

  it('loads documents and supports preview, reindex, reset, and delete', async () => {
    render(<DocumentsPage />)
    await waitFor(() => expect(screen.getByText('policy.pdf')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Preview' }))
    await waitFor(() => expect(screen.getByText('Refund policy text')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Re-index Documents' }))
    await waitFor(() => expect(api.reindexDocuments).toHaveBeenCalledWith(800, 100, 'auto'))

    fireEvent.change(screen.getByLabelText('Chunk Overlap'), { target: { value: '150' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Index Settings' }))
    await waitFor(() => expect(api.updateIndexSettings).toHaveBeenCalledWith(800, 150, 'auto'))

    fireEvent.click(screen.getByRole('button', { name: 'Reset Vector Store' }))
    await waitFor(() => expect(api.resetIndex).toHaveBeenCalledOnce())

    fireEvent.click(screen.getByRole('button', { name: 'Delete Document' }))
    await waitFor(() => expect(api.deleteDocument).toHaveBeenCalledWith(1))
  })
})
