import React, { useEffect, useMemo, useState } from 'react'
import * as api from '../api/client'

const EMPTY_FORM = {
  provider: 'openai',
  model: '',
  base_url: '',
  api_key: '',
  clear_api_key: false
}

const DEFAULT_MODELS = {
  llm: 'gpt-4o-mini',
  embedding: 'text-embedding-3-small'
}

const FALLBACK_PROVIDER_OPTIONS = {
  llm: ['openai', 'gemini', 'anthropic', 'openrouter', 'groq', 'mistral', 'together', 'deepseek', 'xai', 'ollama', 'openai-compatible', 'custom'],
  embedding: ['openai', 'gemini', 'openrouter', 'mistral', 'together', 'deepseek', 'xai', 'ollama', 'openai-compatible', 'custom']
}

const PROVIDER_LABELS = {
  openai: 'OpenAI',
  gemini: 'Google Gemini',
  anthropic: 'Anthropic Claude',
  openrouter: 'OpenRouter',
  groq: 'Groq',
  mistral: 'Mistral',
  together: 'Together AI',
  deepseek: 'DeepSeek',
  xai: 'xAI',
  ollama: 'Ollama',
  'openai-compatible': 'OpenAI-compatible',
  custom: 'Custom'
}

const serviceLabels = {
  llm: 'LLM',
  embedding: 'Embedding'
}

function providerLabel(provider) {
  return PROVIDER_LABELS[provider] || provider
}

function providerHelp(provider, serviceName) {
  if (provider === 'anthropic') {
    return 'Claude is used for answer generation. Choose a separate embedding provider for document vectors.'
  }
  if (provider === 'gemini' && serviceName === 'embedding') {
    return 'Gemini embeddings use Google\'s native embedding API and require re-indexing after model changes.'
  }
  if (provider === 'gemini') {
    return 'Gemini chat uses Google\'s OpenAI-compatible API endpoint.'
  }
  if (provider === 'ollama') {
    return 'Runs against a local Ollama server and does not require an API key.'
  }
  return ''
}

function normalizeSettings(settings, serviceName) {
  return {
    ...EMPTY_FORM,
    provider: settings?.provider || 'openai',
    model: settings?.model || DEFAULT_MODELS[serviceName],
    base_url: settings?.base_url || '',
    api_key: '',
    clear_api_key: false
  }
}

function ProviderCard({ serviceName, form, metadata, providerOptions, modelDefaults, onChange }) {
  const needsBaseUrl = form.provider === 'custom' || form.provider === 'openai-compatible'
  const requiresApiKey = metadata?.requires_api_key !== false && form.provider !== 'ollama'
  const isConfigured = !requiresApiKey || metadata?.api_key_set
  const keyPlaceholder = !requiresApiKey ? 'No key required' : metadata?.api_key_set ? '********' : 'Paste key'
  const help = providerHelp(form.provider, serviceName)

  return (
    <section className="card p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h2 className="text-xl font-semibold">{serviceLabels[serviceName]} provider</h2>
          <p className="text-sm text-gray-500">
            {!requiresApiKey ? 'No key required' : metadata?.api_key_set ? 'Key saved' : 'No key saved'} - {metadata?.source || 'environment'}
          </p>
        </div>
        <span className={`px-3 py-1 rounded-full text-xs font-medium ${isConfigured ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-800'}`}>
          {isConfigured ? 'Configured' : 'Needs key'}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <label className="block">
          <span className="block text-sm font-medium mb-2">Provider</span>
          <select
            value={form.provider}
            onChange={(event) => {
              const provider = event.target.value
              onChange(serviceName, {
                provider,
                model: modelDefaults?.[provider] || form.model,
                base_url: ''
              })
            }}
            className="input-field"
          >
            {providerOptions.map((provider) => (
              <option key={provider} value={provider}>{providerLabel(provider)}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="block text-sm font-medium mb-2">Model</span>
          <input
            value={form.model}
            onChange={(event) => onChange(serviceName, { model: event.target.value })}
            className="input-field"
            autoComplete="off"
            spellCheck={false}
          />
        </label>
      </div>

      {help && (
        <div className="rounded border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
          {help}
        </div>
      )}

      {needsBaseUrl && (
        <label className="block">
          <span className="block text-sm font-medium mb-2">Base URL</span>
          <input
            value={form.base_url}
            onChange={(event) => onChange(serviceName, { base_url: event.target.value })}
            className="input-field"
            placeholder="https://provider.example.com/v1"
            autoComplete="off"
            spellCheck={false}
          />
        </label>
      )}

      <label className="block">
        <span className="block text-sm font-medium mb-2">API key</span>
        <input
          type="password"
          value={form.api_key}
          onChange={(event) => onChange(serviceName, { api_key: event.target.value, clear_api_key: false })}
          className="input-field font-mono"
          placeholder={keyPlaceholder}
          autoComplete="new-password"
          spellCheck={false}
          disabled={!requiresApiKey}
        />
      </label>

      <label className="flex items-center gap-3 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={form.clear_api_key}
          onChange={(event) => onChange(serviceName, { clear_api_key: event.target.checked, api_key: '' })}
          disabled={!requiresApiKey}
        />
        Clear saved key
      </label>
    </section>
  )
}

export default function AISettingsPage() {
  const [providerOptions, setProviderOptions] = useState(FALLBACK_PROVIDER_OPTIONS)
  const [modelDefaults, setModelDefaults] = useState({})
  const [metadata, setMetadata] = useState({})
  const [forms, setForms] = useState({
    llm: { ...EMPTY_FORM, model: DEFAULT_MODELS.llm },
    embedding: { ...EMPTY_FORM, model: DEFAULT_MODELS.embedding }
  })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  const providerLists = useMemo(
    () => ({
      llm: providerOptions?.llm?.length ? providerOptions.llm : FALLBACK_PROVIDER_OPTIONS.llm,
      embedding: providerOptions?.embedding?.length ? providerOptions.embedding : FALLBACK_PROVIDER_OPTIONS.embedding
    }),
    [providerOptions]
  )

  const loadSettings = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.getProviderSettings()
      const data = response.data.data
      setProviderOptions(data.service_provider_options || {
        llm: data.provider_options || FALLBACK_PROVIDER_OPTIONS.llm,
        embedding: data.provider_options || FALLBACK_PROVIDER_OPTIONS.embedding
      })
      setModelDefaults(data.provider_model_defaults || {})
      setMetadata({ llm: data.llm, embedding: data.embedding })
      setForms({
        llm: normalizeSettings(data.llm, 'llm'),
        embedding: normalizeSettings(data.embedding, 'embedding')
      })
    } catch (requestError) {
      setError(api.getErrorMessage(requestError, 'Failed to load AI settings.'))
    } finally {
      setLoading(false)
    }
  }

  const updateForm = (serviceName, patch) => {
    setForms((current) => ({
      ...current,
      [serviceName]: {
        ...current[serviceName],
        ...patch
      }
    }))
  }

  const buildPayloadFor = (serviceName) => {
    const form = forms[serviceName]
    const payload = {
      provider: form.provider,
      model: form.model.trim(),
      base_url: form.base_url.trim() || null,
      clear_api_key: Boolean(form.clear_api_key)
    }
    if (form.api_key.trim()) payload.api_key = form.api_key.trim()
    return payload
  }

  const saveSettings = async () => {
    setSaving(true)
    setMessage('')
    setError('')
    try {
      const response = await api.updateProviderSettings({
        llm: buildPayloadFor('llm'),
        embedding: buildPayloadFor('embedding')
      })
      const data = response.data.data
      setProviderOptions(data.service_provider_options || {
        llm: data.provider_options || FALLBACK_PROVIDER_OPTIONS.llm,
        embedding: data.provider_options || FALLBACK_PROVIDER_OPTIONS.embedding
      })
      setModelDefaults(data.provider_model_defaults || {})
      setMetadata({ llm: data.llm, embedding: data.embedding })
      setForms({
        llm: normalizeSettings(data.llm, 'llm'),
        embedding: normalizeSettings(data.embedding, 'embedding')
      })
      setMessage(data.reindex_required
        ? 'AI settings saved. Embedding settings changed, so documents were marked for re-indexing.'
        : 'AI settings saved.'
      )
    } catch (requestError) {
      setError(api.getErrorMessage(requestError, 'Failed to save AI settings.'))
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">AI Settings</h1>
        <p className="text-gray-600 mt-2">Configure provider credentials used by RAG generation and embeddings.</p>
      </div>

      {error && <div className="card bg-red-50 border-l-4 border-l-red-500 p-4 mb-6 text-sm text-red-700">{error}</div>}
      {message && <div className="card bg-green-50 border-l-4 border-l-green-500 p-4 mb-6 text-sm text-green-700">{message}</div>}

      <div className="grid grid-cols-1 2xl:grid-cols-2 gap-6">
        <ProviderCard
          serviceName="llm"
          form={forms.llm}
          metadata={metadata.llm}
          providerOptions={providerLists.llm}
          modelDefaults={modelDefaults.llm}
          onChange={updateForm}
        />
        <ProviderCard
          serviceName="embedding"
          form={forms.embedding}
          metadata={metadata.embedding}
          providerOptions={providerLists.embedding}
          modelDefaults={modelDefaults.embedding}
          onChange={updateForm}
        />
      </div>

      <div className="mt-6 flex flex-col sm:flex-row gap-3">
        <button
          onClick={saveSettings}
          disabled={loading || saving}
          className="btn-primary disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
        <button
          onClick={loadSettings}
          disabled={loading || saving}
          className="btn-secondary disabled:opacity-50"
        >
          Reload
        </button>
      </div>
    </div>
  )
}
