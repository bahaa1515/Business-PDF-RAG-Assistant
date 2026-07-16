import React from 'react'

export default function SourceCard({ source, rank }) {
  const locatorLabel = source.locator_label || (source.page ? `Page ${source.page}` : 'Document')
  return (
    <div className="card mt-2 border-l-4 border-l-blue-500">
      <div className="flex justify-between items-start mb-2">
        <div>
          <p className="font-semibold text-sm">#{rank} {source.filename}</p>
          <p className="text-xs text-gray-600">{locatorLabel}</p>
        </div>
        {source.score && (
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
            {(source.score * 100).toFixed(1)}%
          </span>
        )}
      </div>
      <p className="text-sm text-gray-700 italic">{source.preview}</p>
    </div>
  )
}
