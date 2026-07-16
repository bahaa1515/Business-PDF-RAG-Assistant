import React, { useEffect, useMemo, useState } from 'react'
import CSVFormatHelp from '../components/CSVFormatHelp'
import * as api from '../api/client'

const MAX_CONFIGURATIONS = 50
const MAX_TOP_K = 20
const SUPPORTED_METHODS = ['similarity', 'mmr', 'hybrid']
const SUPPORTED_RERANKERS = ['none', 'enabled']
const SUPPORTED_CHUNKING_STRATEGIES = ['auto', 'recursive', 'structure', 'table_rows']
const SUPPORTED_PROMPT_VARIANTS = ['baseline_strict', 'grounded_complete', 'policy_procedure', 'multi_doc_synthesis']
const SMART_CONFIGURATION_COUNT = 8

function parseList(input, { allowZero = false, supported = null } = {}) {
  const raw = [...new Set(input.split(',').map((item) => item.trim().toLowerCase()).filter(Boolean))]
  if (!raw.length) return { values: [], error: 'At least one value is required.' }
  if (supported) {
    const unsupported = raw.filter((item) => !supported.includes(item))
    return unsupported.length ? { values: [], error: `Unsupported values: ${unsupported.join(', ')}` } : { values: raw, error: '' }
  }
  const values = raw.map(Number)
  if (values.some((value) => !Number.isInteger(value))) return { values: [], error: 'Use comma-separated integers only.' }
  if (values.some((value) => allowZero ? value < 0 : value <= 0)) return { values: [], error: allowZero ? 'Values must be non-negative.' : 'Values must be positive.' }
  return { values, error: '' }
}

export default function OptimizationPage() {
  const [csvFile, setCsvFile] = useState(null)
  const [questionsCount, setQuestionsCount] = useState(0)
  const [job, setJob] = useState(null)
  const [results, setResults] = useState(null)
  const [message, setMessage] = useState('')
  const [applying, setApplying] = useState(false)
  const [settings, setSettings] = useState({
    search_mode: 'smart',
    semantic_judge: true,
    chunk_sizes: '400,800,1200',
    chunk_overlaps: '50,150',
    top_k_values: '3,5',
    retrieval_methods: 'similarity,hybrid',
    rerankers: 'none',
    chunking_strategies: 'auto,structure',
    prompt_variants: 'grounded_complete'
  })

  useEffect(() => {
    if (!csvFile) return setQuestionsCount(0)
    const reader = new FileReader()
    reader.onload = (event) => setQuestionsCount(Math.max(0, String(event.target.result || '').split(/\r?\n/).filter(Boolean).length - 1))
    reader.readAsText(csvFile)
  }, [csvFile])

  const parsed = useMemo(() => {
    const chunkSizes = parseList(settings.chunk_sizes)
    const chunkOverlaps = parseList(settings.chunk_overlaps, { allowZero: true })
    const topKValues = parseList(settings.top_k_values)
    const retrievalMethods = parseList(settings.retrieval_methods, { supported: SUPPORTED_METHODS })
    const rerankers = parseList(settings.rerankers, { supported: SUPPORTED_RERANKERS })
    const chunkingStrategies = parseList(settings.chunking_strategies, { supported: SUPPORTED_CHUNKING_STRATEGIES })
    const promptVariants = parseList(settings.prompt_variants, { supported: SUPPORTED_PROMPT_VARIANTS })
    const errors = settings.search_mode === 'smart'
      ? []
      : [chunkSizes.error, chunkOverlaps.error, topKValues.error, retrievalMethods.error, rerankers.error, chunkingStrategies.error, promptVariants.error].filter(Boolean)
    if (!['grid', 'smart'].includes(settings.search_mode)) errors.push('Search mode must be grid or smart.')
    if (!errors.length && settings.search_mode === 'grid' && topKValues.values.some((value) => value > MAX_TOP_K)) errors.push(`Top K cannot exceed ${MAX_TOP_K}.`)
    if (!errors.length && settings.search_mode === 'grid') {
      const invalid = chunkSizes.values.flatMap((size) => chunkOverlaps.values.filter((overlap) => overlap >= size).map((overlap) => `${size}/${overlap}`))
      if (invalid.length) errors.push(`Overlap must be smaller than chunk size: ${invalid.join(', ')}`)
    }
    const count = errors.length ? 0 : settings.search_mode === 'smart'
      ? SMART_CONFIGURATION_COUNT
      : chunkSizes.values.length * chunkOverlaps.values.length * topKValues.values.length * retrievalMethods.values.length * rerankers.values.length * chunkingStrategies.values.length * promptVariants.values.length
    if (count > MAX_CONFIGURATIONS) errors.push(`Reduce the search space to ${MAX_CONFIGURATIONS} configurations or fewer.`)
    return { errors, count }
  }, [settings])

  useEffect(() => {
    if (!job?.job_id || ['completed', 'failed', 'cancelled'].includes(job.status)) return undefined
    const timer = window.setInterval(async () => {
      try {
        const response = await api.getOptimizationJob(job.job_id)
        const next = response.data.data
        setJob(next)
        if (next.status === 'completed' || next.status === 'cancelled') {
          setResults(next.result)
          setMessage(next.status === 'completed' ? 'Optimization completed. The previous active index was restored.' : 'Optimization cancelled. Partial results are available.')
        } else if (next.status === 'failed') {
          setMessage(next.error?.message || 'Optimization failed.')
        }
      } catch (error) {
        setMessage(api.getErrorMessage(error))
      }
    }, 1500)
    return () => window.clearInterval(timer)
  }, [job?.job_id, job?.status])

  const handleRun = async () => {
    if (!csvFile || parsed.errors.length) return
    setResults(null)
    setMessage('Queuing background optimization...')
    const formData = new FormData()
    formData.append('csv_file', csvFile)
    Object.entries(settings).forEach(([key, value]) => formData.append(key, value))
    try {
      const response = await api.runOptimization(formData)
      setJob({ job_id: response.data.job_id, status: 'queued', completed_configurations: 0, total_configurations: response.data.total_configurations })
      setMessage('Optimization is running in the background.')
    } catch (error) {
      setMessage(api.getErrorMessage(error))
    }
  }

  const handleCancel = async () => {
    if (!job?.job_id) return
    try {
      await api.cancelOptimizationJob(job.job_id)
      setMessage('Cancellation requested. The current configuration will finish first.')
    } catch (error) {
      setMessage(api.getErrorMessage(error))
    }
  }

  const handleApplyBest = async () => {
    if (!results?.run_id) return
    setApplying(true)
    try {
      const response = await api.applyBestConfiguration(results.run_id)
      const config = response.data.data
      setMessage(`Applied best active index: chunk size ${config.chunk_size}, overlap ${config.chunk_overlap}, strategy ${config.chunking_strategy || 'auto'}.`)
    } catch (error) {
      setMessage(api.getErrorMessage(error))
    } finally {
      setApplying(false)
    }
  }

  const running = job && !['completed', 'failed', 'cancelled'].includes(job.status)
  const progress = job?.total_configurations ? Math.round((job.completed_configurations / job.total_configurations) * 100) : 0

  return (
    <div className="p-4 sm:p-8">
      <div className="mb-8"><h1 className="text-3xl font-bold">Optimization</h1><p className="text-gray-600 mt-2">Safely compare RAG configurations in a bounded background job.</p></div>
      {message && <div className="card mb-6 bg-blue-50 border-l-4 border-l-blue-500 p-4 text-sm text-blue-700">{message}</div>}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        <div className="xl:col-span-1 space-y-6">
          <CSVFormatHelp />
          <div className="card p-6 space-y-3"><label className="block text-sm font-medium">Evaluation CSV</label><input type="file" accept=".csv" onChange={(event) => setCsvFile(event.target.files?.[0] || null)} className="input-field" /></div>
        </div>
        <div className="xl:col-span-3 space-y-6">
          <div className="card p-6 space-y-4">
            <h2 className="text-xl font-semibold">Bounded Search Space</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Search Mode</label>
                <select value={settings.search_mode} onChange={(event) => setSettings({ ...settings, search_mode: event.target.value })} className="input-field">
                  <option value="smart">Smart preset</option>
                  <option value="grid">Grid search</option>
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm md:self-end">
                <input type="checkbox" checked={settings.semantic_judge} onChange={(event) => setSettings({ ...settings, semantic_judge: event.target.checked })} />
                Use semantic judge
              </label>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(settings)
                .filter(([key]) => !['search_mode', 'semantic_judge'].includes(key))
                .map(([key, value]) => <TextSetting key={key} label={key.replaceAll('_', ' ')} value={value} onChange={(next) => setSettings({ ...settings, [key]: next })} />)}
            </div>
            {parsed.errors.map((error) => <p key={error} className="text-sm text-red-700">{error}</p>)}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t"><Metric label="Estimated configurations" value={parsed.count} /><Metric label="Estimated RAG calls" value={parsed.count * questionsCount} /></div>
            <div className="bg-amber-50 rounded-lg p-4 border border-amber-200 text-amber-800 text-sm">Optimization can use API credits. The backend caps runs at {MAX_CONFIGURATIONS} configurations and restores the previous active index when finished.</div>
            {running && <div><div className="flex justify-between text-sm mb-2"><span>{job.status}</span><span>{job.completed_configurations}/{job.total_configurations}</span></div><div className="h-3 bg-gray-200 rounded-full"><div className="h-3 bg-blue-600 rounded-full" style={{ width: `${progress}%` }} /></div></div>}
            <div className="flex flex-col sm:flex-row gap-3">
              <button onClick={handleRun} disabled={running || !csvFile || parsed.errors.length > 0} className="btn-primary flex-1 disabled:opacity-50">{running ? 'Optimization running...' : 'Run Optimization'}</button>
              {running && <button onClick={handleCancel} className="btn-danger w-full sm:w-auto">Cancel</button>}
            </div>
          </div>

          {results?.results && <div className="card p-6 overflow-x-auto">
            <div className="flex items-center justify-between gap-4 mb-4"><div><h2 className="text-xl font-semibold">Ranked Results</h2><p className="text-sm text-gray-600">Active index restored to {formatConfig(results.active_configuration)}.</p></div><button onClick={handleApplyBest} disabled={applying} className="btn-primary disabled:opacity-50">{applying ? 'Applying...' : 'Apply Best Configuration'}</button></div>
            <table className="w-full text-sm min-w-[1900px]"><thead className="bg-gray-100"><tr>{['Rank', 'Chunk', 'Overlap', 'Strategy', 'Top K', 'Method', 'Reranker', 'Prompt', 'Semantic', 'Correctness', 'Faithfulness', 'Context', 'Source Hit', 'Refusal', 'Latency', 'Total', 'Answerable', 'Unanswerable'].map((name) => <th key={name} className="p-3 text-left">{name}</th>)}</tr></thead>
              <tbody>{results.results.map((row) => <tr key={row.rank} className="border-t"><td className="p-3">{row.rank}</td><td className="p-3">{row.chunk_size}</td><td className="p-3">{row.chunk_overlap}</td><td className="p-3">{row.chunking_strategy || 'auto'}</td><td className="p-3">{row.top_k}</td><td className="p-3">{row.retrieval_method}</td><td className="p-3">{row.reranker}</td><td className="p-3">{formatValue(row.prompt_variant || 'grounded_complete')}</td><td className="p-3">{row.semantic_answer_correctness === null || row.semantic_answer_correctness === undefined ? '-' : percent(row.semantic_answer_correctness)}</td><td className="p-3">{percent(row.answer_correctness)}</td><td className="p-3">{percent(row.faithfulness)}</td><td className="p-3">{percent(row.context_relevance)}</td><td className="p-3">{percent(row.source_hit_rate)}</td><td className="p-3">{percent(row.refusal_accuracy)}</td><td className="p-3">{row.average_latency.toFixed(2)}s</td><td className="p-3">{row.total_questions}</td><td className="p-3">{row.answerable_questions}</td><td className="p-3">{row.unanswerable_questions}</td></tr>)}</tbody>
            </table>
          </div>}
        </div>
      </div>
    </div>
  )
}

function TextSetting({ label, value, onChange }) {
  return <div><label className="block text-sm font-medium mb-1 capitalize">{label}</label><input type="text" value={value} onChange={(event) => onChange(event.target.value)} className="input-field" /></div>
}
function Metric({ label, value }) {
  return <div className="bg-gray-50 rounded-lg p-4"><p className="text-sm text-gray-600">{label}</p><p className="text-3xl font-semibold">{value}</p></div>
}
function percent(value) { return `${((value || 0) * 100).toFixed(1)}%` }
function formatValue(value) { return String(value || '').replaceAll('_', ' ') }
function formatConfig(config) { return config ? `${config.chunk_size}/${config.chunk_overlap}/${config.chunking_strategy || 'auto'}` : 'no prior configuration' }
