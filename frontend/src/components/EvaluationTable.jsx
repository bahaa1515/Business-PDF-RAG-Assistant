import React from 'react'

export default function EvaluationTable({ results }) {
  if (!results || results.length === 0) return null

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b">
          <th className="text-left py-2">Question</th>
          <th className="text-left py-2">Result</th>
        </tr>
      </thead>
      <tbody>
        {results.map((result, index) => (
          <tr key={index} className="border-b">
            <td className="py-2">{result.question}</td>
            <td className="py-2">{result.source_hit ? 'Yes' : 'No'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
