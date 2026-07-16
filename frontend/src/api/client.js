import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8081'
let csrfToken = ''

export const setCsrfToken = (token = '') => {
  csrfToken = token || ''
}

const client = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json'
  }
})

client.interceptors.request.use((config) => {
  const method = (config.method || 'get').toLowerCase()
  if (csrfToken && ['post', 'put', 'patch', 'delete'].includes(method)) {
    config.headers['X-CSRF-Token'] = csrfToken
  }
  return config
})

// Authentication
export const login = (role, password = '') =>
  client.post('/auth/login', { role, password })

export const getSession = () => client.get('/auth/me')

export const logout = () => client.post('/auth/logout')

// Health
export const getHealth = () => client.get('/health')

// Documents
export const uploadDocuments = (files) => {
  const formData = new FormData()
  files.forEach(file => formData.append('files', file))
  return client.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const getDocuments = () => client.get('/documents/')

export const getIndexStatus = () => client.get('/documents/index-status')

export const updateIndexSettings = (chunkSize = 800, chunkOverlap = 100, chunkingStrategy = 'auto') =>
  client.put('/documents/index-settings', {
    chunk_size: chunkSize,
    chunk_overlap: chunkOverlap,
    chunking_strategy: chunkingStrategy
  })

export const getDocumentPreview = (id) => client.get(`/documents/${id}/preview`)

export const deleteDocument = (id) => client.delete(`/documents/${id}`)

export const reindexDocuments = (chunkSize = 800, chunkOverlap = 100, chunkingStrategy = 'auto') =>
  client.post('/documents/reindex', {}, {
    params: { chunk_size: chunkSize, chunk_overlap: chunkOverlap, chunking_strategy: chunkingStrategy }
  })

export const resetIndex = () => client.post('/documents/reset-index')

// Chat
export const chat = (
  question,
  topK = 5,
  retrievalMethod = 'similarity',
  reranker = 'none',
  showDebug = false,
  retrievalProfile = 'manual',
  answerVerification = false
) =>
  client.post('/chat/', {
    question,
    top_k: topK,
    retrieval_method: retrievalMethod,
    reranker,
    retrieval_profile: retrievalProfile,
    answer_verification: answerVerification,
    show_debug: showDebug
  })

export const getChatHistory = (limit = 50) =>
  client.get('/chat/history', { params: { limit } })

export const clearChatHistory = () => client.delete('/chat/history')

export const submitFeedback = (chatLogId, rating, comment = '') =>
  client.post('/feedback', { chat_log_id: chatLogId, rating, comment })

export const getFailedQuestionAnalytics = () => client.get('/analytics/failed-questions')

export const clearFailedQuestionAnalytics = () => client.delete('/analytics/failed-questions')

// Admin provider settings
export const getProviderSettings = () => client.get('/admin/provider-settings/')

export const updateProviderSettings = (settings) =>
  client.put('/admin/provider-settings/', settings)

// Evaluation
export const runEvaluation = (csvFile = null, settings = {}) => {
  const formData = new FormData()
  if (csvFile) formData.append('csv_file', csvFile)
  formData.append('chunk_size', settings.chunk_size || 800)
  formData.append('chunk_overlap', settings.chunk_overlap || 100)
  formData.append('top_k', settings.top_k || 5)
  formData.append('retrieval_method', settings.retrieval_method || 'similarity')
  formData.append('reranker', settings.reranker || 'none')
  formData.append('chunking_strategy', settings.chunking_strategy || 'auto')
  formData.append('prompt_variant', settings.prompt_variant || 'grounded_complete')
  formData.append('semantic_judge', settings.semantic_judge ? 'true' : 'false')
  formData.append('retrieval_profile', settings.retrieval_profile || 'manual')
  formData.append('answer_verification', settings.answer_verification ? 'true' : 'false')
  formData.append('benchmark_split', settings.benchmark_split || 'known')
  return client.post('/evaluation/run', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const getLatestEvaluation = () => client.get('/evaluation/latest')

export const judgeEvaluation = (runId) => client.post(`/evaluation/${runId}/semantic-judge`)

export const runOptimization = (formData) =>
  client.post('/optimization/run', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })

export const getOptimizationJob = (jobId) => client.get(`/optimization/jobs/${jobId}`)

export const cancelOptimizationJob = (jobId) => client.post(`/optimization/jobs/${jobId}/cancel`)

export const applyBestConfiguration = (runId) => client.post(`/optimization/runs/${runId}/apply-best`)

export const getErrorMessage = (error, fallback = 'Request failed.') => {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(', ') || fallback
  return error.message || fallback
}

