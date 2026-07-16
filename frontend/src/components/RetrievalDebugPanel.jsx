import React from 'react'

export default function RetrievalDebugPanel({ chunks }) {
  if (!chunks?.length) return null
  return (
    <div className="card mt-4 bg-gray-50">
      <h4 className="font-semibold mb-3 text-sm">Retrieved Chunks (Admin Debug)</h4>
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {chunks.map((chunk, index) => {
          const locatorLabel = chunk.locator_label || (chunk.page ? `Page ${chunk.page}` : 'Document')
          return (
          <div key={index} className="text-xs bg-white p-3 rounded border border-gray-200">
            <div className="flex justify-between mb-2">
              <span className="font-medium">#{chunk.rank} - {chunk.filename} ({locatorLabel})</span>
              {chunk.score !== undefined && <span className="text-blue-600">{(chunk.score * 100).toFixed(1)}%</span>}
            </div>
            <p className="text-gray-700 break-words">{chunk.preview}</p>
          </div>
          )
        })}
      </div>
    </div>
  )
}
