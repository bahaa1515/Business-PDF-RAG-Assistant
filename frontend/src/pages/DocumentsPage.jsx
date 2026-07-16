import React, { useEffect, useState } from 'react'
import UploadPanel from '../components/UploadPanel'
import * as api from '../api/client'

const DEFAULT_CHUNK_SIZE = 800
const DEFAULT_CHUNK_OVERLAP = 100
const DEFAULT_CHUNKING_STRATEGY = 'auto'
const CHUNKING_STRATEGIES = ['auto', 'recursive', 'structure', 'table_rows']

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [rejectedFiles, setRejectedFiles] = useState([])
  const [chunkSize, setChunkSize] = useState(DEFAULT_CHUNK_SIZE)
  const [chunkOverlap, setChunkOverlap] = useState(DEFAULT_CHUNK_OVERLAP)
  const [chunkingStrategy, setChunkingStrategy] = useState(DEFAULT_CHUNKING_STRATEGY)
  const [indexStatus, setIndexStatus] = useState(null)
  const [previews, setPreviews] = useState({})
  const [previewLoadingId, setPreviewLoadingId] = useState(null)
  const needsReindex = indexStatus ? !indexStatus.ready : documents.some((doc) => doc.status === 'needs_reindex')
  const indexValidationError = getIndexValidationError(chunkSize, chunkOverlap, chunkingStrategy)

  const loadDocuments = async () => {
    setLoading(true)
    try {
      const [documentsResponse, indexStatusResponse] = await Promise.all([
        api.getDocuments(),
        api.getIndexStatus()
      ])
      setDocuments(documentsResponse.data.documents || [])
      const status = indexStatusResponse.data.data
      setIndexStatus(status)
      if (status?.configuration) {
        setChunkSize(status.configuration.chunk_size || DEFAULT_CHUNK_SIZE)
        setChunkOverlap(status.configuration.chunk_overlap ?? DEFAULT_CHUNK_OVERLAP)
        setChunkingStrategy(status.configuration.chunking_strategy || DEFAULT_CHUNKING_STRATEGY)
      }
    } catch (error) {
      setMessage(`Error loading documents: ${api.getErrorMessage(error)}`)
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (files) => {
    try {
      const response = await api.uploadDocuments(files)
      const totalUploaded = response.data.total_uploaded ?? response.data.total ?? 0
      const totalRejected = response.data.total_rejected ?? 0
      setRejectedFiles(response.data.rejected_files || [])
      setMessage(`Uploaded ${totalUploaded} file(s). Rejected ${totalRejected} unsafe or unsupported file(s).`)
      await loadDocuments()
    } catch (error) {
      setMessage(`Upload failed: ${api.getErrorMessage(error)}`)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this document and its indexed vectors?')) return
    try {
      await api.deleteDocument(id)
      setMessage('Document deleted.')
      setPreviews((current) => {
        const next = { ...current }
        delete next[id]
        return next
      })
      await loadDocuments()
    } catch (error) {
      setMessage(`Delete failed: ${api.getErrorMessage(error)}`)
    }
  }

  const handlePreview = async (id) => {
    if (previews[id]) {
      setPreviews((current) => ({ ...current, [id]: null }))
      return
    }
    setPreviewLoadingId(id)
    try {
      const response = await api.getDocumentPreview(id)
      setPreviews((current) => ({ ...current, [id]: response.data.data }))
    } catch (error) {
      setMessage(`Preview failed: ${api.getErrorMessage(error)}`)
    } finally {
      setPreviewLoadingId(null)
    }
  }

  const handleReindex = async () => {
    if (indexValidationError) return
    setLoading(true)
    setMessage('Re-indexing documents...')
    try {
      const response = await api.reindexDocuments(chunkSize, chunkOverlap, chunkingStrategy)
      setMessage(`Re-indexed successfully with ${formatStrategy(chunkingStrategy)} chunking. Total chunks: ${response.data.result.total_chunks}`)
      await loadDocuments()
    } catch (error) {
      setMessage(`Re-index failed: ${api.getErrorMessage(error)}`)
    } finally {
      setLoading(false)
    }
  }

  const handleSaveIndexSettings = async () => {
    if (indexValidationError) return
    setLoading(true)
    try {
      const response = await api.updateIndexSettings(chunkSize, chunkOverlap, chunkingStrategy)
      const data = response.data.data
      setMessage(data.reindex_required
        ? `Index settings saved. ${data.stale_documents} document(s) now need re-indexing.`
        : 'Index settings saved.')
      await loadDocuments()
    } catch (error) {
      setMessage(`Index settings failed: ${api.getErrorMessage(error)}`)
    } finally {
      setLoading(false)
    }
  }

  const handleResetIndex = async () => {
    if (!confirm('Reset the vector store? This clears every indexed chunk.')) return
    setLoading(true)
    try {
      await api.resetIndex()
      setMessage('Vector store reset.')
      await loadDocuments()
    } catch (error) {
      setMessage(`Reset failed: ${api.getErrorMessage(error)}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDocuments()
  }, [])

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Documents</h1>
        <p className="text-gray-600 mt-2">Upload, preview, re-index, and reset the document knowledge base.</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 mb-6">
        <div className="xl:col-span-1 space-y-4">
          <UploadPanel onUpload={handleUpload} />
          <div className="card p-6 space-y-4">
            <h2 className="text-lg font-semibold">Admin maintenance</h2>
            <div>
              <label htmlFor="document-chunk-size" className="block text-sm font-medium mb-2">Chunk Size</label>
              <input
                id="document-chunk-size"
                type="number"
                min="1"
                value={chunkSize}
                onChange={(event) => setChunkSize(Number(event.target.value))}
                className="input-field"
              />
            </div>
            <div>
              <label htmlFor="document-chunk-overlap" className="block text-sm font-medium mb-2">Chunk Overlap</label>
              <input
                id="document-chunk-overlap"
                type="number"
                min="0"
                value={chunkOverlap}
                onChange={(event) => setChunkOverlap(Number(event.target.value))}
                className="input-field"
              />
            </div>
            <div>
              <label htmlFor="document-chunking-strategy" className="block text-sm font-medium mb-2">Chunking Strategy</label>
              <select
                id="document-chunking-strategy"
                value={chunkingStrategy}
                onChange={(event) => setChunkingStrategy(event.target.value)}
                className="input-field"
              >
                {CHUNKING_STRATEGIES.map((strategy) => (
                  <option key={strategy} value={strategy}>{formatStrategy(strategy)}</option>
                ))}
              </select>
            </div>
            {indexValidationError && <p className="text-sm text-red-700">{indexValidationError}</p>}
            <button
              onClick={handleSaveIndexSettings}
              disabled={loading || Boolean(indexValidationError)}
              className="btn-secondary w-full disabled:opacity-50"
            >
              Save Index Settings
            </button>
            <button
              onClick={handleReindex}
              disabled={loading || documents.length === 0 || Boolean(indexValidationError)}
              className="btn-primary w-full disabled:opacity-50"
            >
              Re-index Documents
            </button>
            <button
              onClick={handleResetIndex}
              disabled={loading}
              className="btn-danger w-full disabled:opacity-50"
            >
              Reset Vector Store
            </button>
          </div>
        </div>

        <div className="xl:col-span-3 space-y-4">
          {message && (
            <div className="card bg-blue-50 border-l-4 border-l-blue-500 p-4">
              <p className="text-sm text-blue-700">{message}</p>
            </div>
          )}

          {needsReindex && (
            <div className="card bg-amber-50 border-l-4 border-l-amber-500 p-4">
              <p className="text-sm font-semibold text-amber-900">Documents need re-indexing</p>
              <p className="text-sm text-amber-800 mt-1">
                The embedding or chunking configuration changed. Re-index documents before chat uses the current configuration.
              </p>
            </div>
          )}

          {rejectedFiles.length > 0 && (
            <div className="card bg-amber-50 border-l-4 border-l-amber-500 p-4">
              <p className="text-sm font-semibold text-amber-900 mb-2">Rejected upload entries</p>
              <ul className="space-y-1 text-sm text-amber-800">
                {rejectedFiles.map((item, index) => (
                  <li key={`${item.filename}-${index}`}>{item.filename}: {item.reason}</li>
                ))}
              </ul>
            </div>
          )}

          {documents.length === 0 && !loading && (
            <div className="card text-center py-8 text-gray-600">No documents uploaded yet.</div>
          )}

          {documents.map((doc) => {
            const preview = previews[doc.id]
            return (
              <div key={doc.id} className="card p-6">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-4">
                  <div>
                    <h3 className="font-semibold text-lg">{doc.filename}</h3>
                    <p className="text-sm text-gray-500 mt-1">
                      Uploaded: {doc.upload_time ? new Date(doc.upload_time).toLocaleString() : 'Unknown'}
                    </p>
                  </div>
                  <span className="px-3 py-1 text-xs rounded-full font-medium bg-gray-100 text-gray-700">
                    {doc.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-4 text-sm">
                  <div><p className="font-semibold">Type</p><p className="uppercase">{doc.document_type || 'pdf'}</p></div>
                  <div><p className="font-semibold">Pages</p><p>{doc.page_count || 0}</p></div>
                  <div><p className="font-semibold">Units</p><p>{doc.content_unit_count || 0}</p></div>
                  <div><p className="font-semibold">Chunks</p><p>{doc.chunk_count || 0}</p></div>
                  <div><p className="font-semibold">Chunking</p><p>{formatStrategy(doc.chunking_strategy || 'auto')}</p></div>
                  <div><p className="font-semibold">Indexed status</p><p>{doc.status === 'indexed' ? 'Indexed' : 'Not indexed'}</p></div>
                </div>

                <div className="flex flex-col sm:flex-row gap-3">
                  <button onClick={() => handlePreview(doc.id)} className="btn-secondary flex-1">
                    {previewLoadingId === doc.id ? 'Loading preview...' : preview ? 'Hide Preview' : 'Preview'}
                  </button>
                  <button onClick={() => handleDelete(doc.id)} className="btn-danger flex-1">
                    Delete Document
                  </button>
                </div>

                {preview && (
                  <div className="mt-4 bg-gray-50 rounded-lg p-4 space-y-4 text-sm">
                    <div>
                      <p className="font-semibold mb-1">First extracted text</p>
                      <p className="whitespace-pre-wrap text-gray-700">{preview.first_text_preview || 'No extractable text found.'}</p>
                    </div>
                    <div>
                      <p className="font-semibold mb-2">First chunk previews</p>
                      <div className="space-y-2">
                        {preview.chunk_previews?.map((chunk) => (
                          <div key={chunk.chunk_id} className="bg-white border border-gray-200 rounded p-3">
                            <p className="font-medium">{chunk.locator_label || (chunk.page ? `Page ${chunk.page}` : 'Document')}, chunk {chunk.chunk_id}</p>
                            <p className="text-gray-700 mt-1">{chunk.preview}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function formatStrategy(strategy) {
  return String(strategy || 'auto').replaceAll('_', ' ')
}

function getIndexValidationError(chunkSize, chunkOverlap, chunkingStrategy) {
  if (chunkSize <= 0) return 'Chunk Size must be positive.'
  if (chunkOverlap < 0) return 'Chunk Overlap must be non-negative.'
  if (chunkOverlap >= chunkSize) return 'Chunk Overlap must be smaller than Chunk Size.'
  if (!CHUNKING_STRATEGIES.includes(chunkingStrategy)) return 'Select a supported chunking strategy.'
  return ''
}
