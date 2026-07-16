import React, { useEffect, useMemo, useState } from 'react'
import CSVFormatHelp from '../components/CSVFormatHelp'
import * as api from '../api/client'

const CHUNKING_STRATEGIES = ['auto', 'recursive', 'structure', 'table_rows']
const PROMPT_VARIANTS = ['baseline_strict', 'grounded_complete', 'policy_procedure', 'multi_doc_synthesis']
const RETRIEVAL_PROFILES = ['manual', 'auto']
const BENCHMARK_SPLITS = ['known', 'holdout', 'custom']

export default function EvaluationPage() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [csvFile, setCsvFile] = useState(null)
  const [message, setMessage] = useState('')
  const [judging, setJudging] = useState(false)
  const [settings, setSettings] = useState({
    chunk_size: 800,
    chunk_overlap: 150,
    top_k: 5,
    retrieval_method: 'hybrid',
    reranker: 'none',
    chunking_strategy: 'structure',
    prompt_variant: 'grounded_complete',
    semantic_judge: false,
    retrieval_profile: 'auto',
    answer_verification: false,
    benchmark_split: 'known'
  })

  const validationError = useMemo(() => {
    if (settings.chunk_size <= 0) return 'Chunk Size must be positive.'
    if (settings.chunk_overlap < 0) return 'Chunk Overlap must be non-negative.'
    if (settings.chunk_overlap >= settings.chunk_size) return 'Chunk Overlap must be smaller than Chunk Size.'
    if (settings.top_k <= 0 || settings.top_k > 20) return 'Top K must be between 1 and 20.'
    if (!CHUNKING_STRATEGIES.includes(settings.chunking_strategy)) return 'Select a supported chunking strategy.'
    if (!PROMPT_VARIANTS.includes(settings.prompt_variant)) return 'Select a supported prompt variant.'
    if (!RETRIEVAL_PROFILES.includes(settings.retrieval_profile)) return 'Select a supported retrieval profile.'
    if (!BENCHMARK_SPLITS.includes(settings.benchmark_split)) return 'Select a supported benchmark split.'
    return ''
  }, [settings])

  useEffect(() => {
    let mounted = true
    api.getLatestEvaluation()
      .then((response) => {
        if (!mounted || !response.data.data) return
        setResults(response.data.data)
        setMessage('Loaded latest saved evaluation run.')
      })
      .catch(() => {})
    return () => {
      mounted = false
    }
  }, [])

  const handleRunEvaluation = async () => {
    if (!csvFile || validationError) return
    setLoading(true)
    setMessage('Running evaluation...')
    try {
      const response = await api.runEvaluation(csvFile, settings)
      setResults(response.data.data)
      setMessage(response.data.data.index_result?.reindexed
        ? 'Evaluation completed after re-indexing for the selected chunk configuration.'
        : 'Evaluation completed using the current index configuration.')
    } catch (error) {
      setMessage(api.getErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }

  const handleRunSemanticJudge = async () => {
    if (!results?.run_id) return
    setJudging(true)
    setMessage('Scoring saved answers with the configured LLM judge...')
    try {
      const response = await api.judgeEvaluation(results.run_id)
      setResults(response.data.data)
      setMessage('Semantic answer correctness updated for the saved evaluation run.')
    } catch (error) {
      setMessage(api.getErrorMessage(error, 'Semantic judge failed.'))
    } finally {
      setJudging(false)
    }
  }

  return (
    <div className="p-4 sm:p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Evaluation</h1>
        <p className="text-gray-600 mt-2">Test one selected RAG configuration using a labeled CSV dataset.</p>
      </div>

      {message && <div className="card mb-6 bg-blue-50 border-l-4 border-l-blue-500 p-4 text-sm text-blue-700">{message}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 mb-6">
        <div className="xl:col-span-1 space-y-6">
          <CSVFormatHelp />
          <div className="card p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Evaluation CSV</label>
              <input type="file" accept=".csv" onChange={(event) => setCsvFile(event.target.files?.[0] || null)} className="input-field w-full" />
              <p className="text-xs text-gray-500 mt-1">A valid labeled CSV is required.</p>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Benchmark Split</label>
              <select value={settings.benchmark_split} onChange={(event) => setSettings({ ...settings, benchmark_split: event.target.value })} className="input-field">
                <option value="known">Known benchmark</option>
                <option value="holdout">Unseen holdout</option>
                <option value="custom">Custom client-style set</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Chunk Size</label>
              <input type="number" min="1" value={settings.chunk_size} onChange={(event) => setSettings({ ...settings, chunk_size: Number(event.target.value) })} className="input-field" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Chunk Overlap</label>
              <input type="number" min="0" value={settings.chunk_overlap} onChange={(event) => setSettings({ ...settings, chunk_overlap: Number(event.target.value) })} className="input-field" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Chunking Strategy</label>
              <select value={settings.chunking_strategy} onChange={(event) => setSettings({ ...settings, chunking_strategy: event.target.value })} className="input-field">
                {CHUNKING_STRATEGIES.map((strategy) => (
                  <option key={strategy} value={strategy}>{formatStrategy(strategy)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Top K</label>
              <input type="number" min="1" value={settings.top_k} onChange={(event) => setSettings({ ...settings, top_k: Number(event.target.value) })} className="input-field" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Retrieval Profile</label>
              <select value={settings.retrieval_profile} onChange={(event) => setSettings({ ...settings, retrieval_profile: event.target.value })} className="input-field">
                <option value="manual">Manual settings</option>
                <option value="auto">Auto by question type</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Retrieval Method</label>
              <select value={settings.retrieval_method} onChange={(event) => setSettings({ ...settings, retrieval_method: event.target.value })} className="input-field">
                <option value="similarity">Similarity</option>
                <option value="mmr">MMR</option>
                <option value="hybrid">Hybrid vector + keyword</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Reranker</label>
              <select value={settings.reranker} onChange={(event) => setSettings({ ...settings, reranker: event.target.value })} className="input-field">
                <option value="none">None</option>
                <option value="enabled">Enabled</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Prompt Variant</label>
              <select value={settings.prompt_variant} onChange={(event) => setSettings({ ...settings, prompt_variant: event.target.value })} className="input-field">
                {PROMPT_VARIANTS.map((variant) => (
                  <option key={variant} value={variant}>{formatStrategy(variant)}</option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={settings.semantic_judge} onChange={(event) => setSettings({ ...settings, semantic_judge: event.target.checked })} />
              Score semantic correctness during run
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={settings.answer_verification} onChange={(event) => setSettings({ ...settings, answer_verification: event.target.checked })} />
              Verify answers before scoring
            </label>
            {validationError && <p className="text-sm text-red-700">{validationError}</p>}
            <button onClick={handleRunEvaluation} disabled={loading || !csvFile || Boolean(validationError)} className="btn-primary w-full disabled:opacity-50">
              {loading ? 'Running evaluation...' : 'Run Evaluation'}
            </button>
          </div>
        </div>

        <div className="xl:col-span-3 space-y-6">
          {!results ? (
            <div className="card p-6 text-gray-600">Upload a CSV and run evaluation to see results here.</div>
          ) : (
            <div className="space-y-6">
              <div className="card p-6">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h2 className="text-xl font-semibold">RAG Quality Summary</h2>
                    <p className="mt-1 text-sm text-gray-600">
                      Main metrics focus on whether the right sources were retrieved, whether answers match the reference semantically, and whether unavailable answers were refused.
                    </p>
                  </div>
                  <button
                    onClick={handleRunSemanticJudge}
                    disabled={judging || !results.run_id}
                    className="btn-secondary disabled:opacity-50"
                  >
                    {judging ? 'Scoring...' : 'Run Semantic Judge'}
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                <Metric label="Retrieval Accuracy" value={`${(results.source_hit_rate * 100).toFixed(1)}%`} />
                <Metric label="Semantic Correctness" value={formatScore(results.semantic_answer_correctness, 'Not judged')} />
                <Metric label="Refusal Accuracy" value={`${(results.refusal_accuracy * 100).toFixed(1)}%`} />
                <Metric label="Average Latency" value={`${results.average_latency.toFixed(2)}s`} />
                <Metric label="Benchmark Split" value={formatStrategy(results.benchmark_split || results.configuration?.benchmark_split || 'known')} />
                <Metric label="Retrieval Profile" value={formatStrategy(results.retrieval_profile || results.configuration?.retrieval_profile || 'manual')} />
                <Metric label="Answer Verification" value={results.answer_verification ? 'Enabled' : 'Off'} />
                <Metric label="LLM Model" value={results.llm_model || 'Not recorded'} />
                <Metric label="Embedding Model" value={results.embedding_model || 'Not recorded'} />
                <Metric label="Prompt Variant" value={formatStrategy(results.prompt_variant || results.configuration?.prompt_variant || 'grounded_complete')} />
                <Metric label="Questions Tested" value={results.total_questions} />
                <Metric label="Answerable" value={results.answerable_questions} />
                <Metric label="Unanswerable" value={results.unanswerable_questions} />
              </div>

              <div className="card p-6 overflow-x-auto">
                <table className="w-full text-sm border-collapse min-w-[1700px]">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="p-3 text-left">Question</th>
                      <th className="p-3 text-left">Type</th>
                      <th className="p-3 text-left">Reference Answer</th>
                      <th className="p-3 text-left">Expected Source</th>
                      <th className="p-3 text-left">Expected Locator</th>
                      <th className="p-3 text-left">Retrieved Sources</th>
                      <th className="p-3 text-center">Retrieval Hit</th>
                      <th className="p-3 text-center">Correctly Refused</th>
                      <th className="p-3 text-right">Semantic Score</th>
                      <th className="p-3 text-left">Judge Verdict</th>
                      <th className="p-3 text-left">Judge Reason</th>
                      <th className="p-3 text-left">Prompt</th>
                      <th className="p-3 text-left">Retrieval</th>
                      <th className="p-3 text-center">Verified</th>
                      <th className="p-3 text-right">Latency</th>
                      <th className="p-3 text-left">Generated Answer</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.results.map((row, index) => (
                      <tr key={index} className="border-t border-gray-200 align-top">
                        <td className="p-3 max-w-xs">{row.question}</td>
                        <td className="p-3">{row.question_type}</td>
                        <td className="p-3 max-w-xs">{row.reference_answer || '-'}</td>
                        <td className="p-3">{row.expected_source || '-'}</td>
                        <td className="p-3">{row.expected_locator || (row.expected_page ? `Page ${row.expected_page}` : '-')}</td>
                        <td className="p-3">{row.retrieved_sources?.map((source, sourceIndex) => <div key={sourceIndex}>{source.filename} ({formatLocator(source)})</div>)}</td>
                        <td className="p-3 text-center">{formatBoolean(row.source_hit)}</td>
                        <td className="p-3 text-center">{formatBoolean(row.correctly_refused)}</td>
                        <td className="p-3 text-right">{formatScore(row.semantic_answer_correctness)}</td>
                        <td className="p-3 capitalize">{row.semantic_verdict || '-'}</td>
                        <td className="p-3 max-w-sm">{row.semantic_explanation || '-'}</td>
                        <td className="p-3">{formatStrategy(row.prompt_variant || results.prompt_variant || 'grounded_complete')}</td>
                        <td className="p-3">{formatRowRetrieval(row)}</td>
                        <td className="p-3 text-center">{row.answer_verification ? 'Yes' : 'No'}</td>
                        <td className="p-3 text-right">{row.latency.toFixed(2)}s</td>
                        <td className="p-3 max-w-md whitespace-pre-wrap">{row.generated_answer}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value }) {
  return <div className="card p-4"><p className="text-sm text-gray-600">{label}</p><p className="text-2xl font-semibold">{value}</p></div>
}

function formatBoolean(value) {
  if (value === null || value === undefined) return '-'
  return value ? 'Yes' : 'No'
}

function formatScore(value, emptyLabel = '-') {
  if (value === null || value === undefined) return emptyLabel
  return `${(value * 100).toFixed(1)}%`
}

function formatLocator(source) {
  return source.locator_label || (source.page ? `Page ${source.page}` : 'Document')
}

function formatStrategy(strategy) {
  return String(strategy || 'auto').replaceAll('_', ' ')
}

function formatRowRetrieval(row) {
  const profile = row.resolved_retrieval_profile || row.retrieval_profile || 'manual'
  const method = row.retrieval_method || '-'
  const topK = row.top_k ? `Top K ${row.top_k}` : 'Top K -'
  return `${formatStrategy(profile)} | ${method} | ${topK}`
}
