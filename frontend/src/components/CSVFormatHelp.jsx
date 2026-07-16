import React from 'react'

const SAMPLE_CSV = `question,reference_answer,expected_source,expected_page,question_type,expected_locator
"What is the refund window?","Customers may request a refund within 30 days.",refund_policy.pdf,1,answerable,
"Which rows list enterprise support regions?","Rows 2-10 list the support regions.",support_regions.xlsx,,product_technical_documentation,"Support, Rows 2-10"
"What is the company's stock price today?","The answer is not available in the provided documents.",none,none,unanswerable,
`

export default function CSVFormatHelp() {
  const downloadSample = () => {
    const blob = new Blob([SAMPLE_CSV], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'sample_evaluation.csv'
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="card p-6 space-y-4 bg-blue-50 border-l-4 border-l-blue-500">
      <div>
        <h2 className="text-xl font-semibold">CSV Format</h2>
        <p className="text-sm text-gray-700 mt-2">The CSV must contain five required columns, plus optional expected_locator for non-PDF citations.</p>
      </div>

      <div className="text-sm text-gray-700 space-y-2">
        <p><strong>question</strong>: the question to ask the RAG system.</p>
        <p><strong>reference_answer</strong>: the expected grounded answer, or the standard unavailable answer for unanswerable rows.</p>
        <p><strong>expected_source</strong>: the exact uploaded document filename expected to contain the answer.</p>
        <p><strong>expected_page</strong>: the positive PDF page number expected to contain the answer.</p>
        <p><strong>question_type</strong>: any useful answerable category, or <code>unanswerable</code>.</p>
        <p><strong>expected_locator</strong>: optional section, heading, sheet, or row-range locator for non-PDF documents.</p>
      </div>

      <div className="text-sm text-gray-700 space-y-1">
        <p>Answerable rows require reference_answer, expected_source, and either expected_page or expected_locator.</p>
        <p>Unanswerable rows can leave expected fields empty or use <code>none</code>.</p>
      </div>

      <pre className="bg-white rounded-lg p-4 text-xs overflow-x-auto text-gray-800">{SAMPLE_CSV}</pre>

      <button type="button" onClick={downloadSample} className="btn-secondary w-full sm:w-auto">
        Download sample CSV
      </button>
    </div>
  )
}
