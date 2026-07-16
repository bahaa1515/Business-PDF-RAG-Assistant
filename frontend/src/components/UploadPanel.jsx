import React, { useState } from 'react'

const SUPPORTED_ACCEPT = '.pdf,.docx,.txt,.md,.html,.htm,.csv,.xlsx,.zip'
const SUPPORTED_LABEL = 'PDF, DOCX, TXT, MD, HTML, CSV, XLSX, ZIP'

export default function UploadPanel({ onUpload }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)

  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files || []))
  }

  const handleUpload = async () => {
    if (files.length === 0) return
    setLoading(true)
    try {
      await onUpload(files)
      setFiles([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h3 className="font-semibold mb-4">Upload Documents</h3>

      <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-500 transition-colors mb-4">
        <input
          type="file"
          multiple
          accept={SUPPORTED_ACCEPT}
          onChange={handleFileChange}
          disabled={loading}
          className="hidden"
          id="file-input"
        />
        <label htmlFor="file-input" className="cursor-pointer">
          <div className="text-sm uppercase tracking-wide text-blue-700 font-semibold mb-2">
            Business documents
          </div>
          <p className="text-gray-700 font-medium">Select business documents</p>
          <p className="text-sm text-gray-500 mt-1">{SUPPORTED_LABEL}</p>
        </label>
      </div>

      {files.length > 0 && (
        <div className="mb-4">
          <p className="text-sm font-medium mb-2">{files.length} file(s) selected:</p>
          <ul className="space-y-1 text-sm text-gray-600">
            {files.map((file, index) => (
              <li key={`${file.name}-${index}`}>Selected: {file.name}</li>
            ))}
          </ul>
        </div>
      )}

      <button
        onClick={handleUpload}
        disabled={files.length === 0 || loading}
        className="btn-primary disabled:opacity-50 w-full"
      >
        {loading ? 'Uploading...' : 'Upload'}
      </button>
    </div>
  )
}
