import React from 'react'

export default function SettingsPanel({ settings, onSettingsChange }) {
  const handleChange = (key, value) => onSettingsChange({ ...settings, [key]: value })

  return (
    <div className="card">
      <h3 className="font-semibold mb-4">Chat Settings</h3>
      <div className="space-y-4">
        <div>
          <label htmlFor="chat-top-k" className="block text-sm font-medium mb-2">Top K: {settings.top_k}</label>
          <input id="chat-top-k" type="range" min="1" max="20" value={settings.top_k} onChange={(event) => handleChange('top_k', parseInt(event.target.value, 10))} className="w-full" />
        </div>
        <div>
          <label htmlFor="chat-retrieval-profile" className="block text-sm font-medium mb-2">Retrieval Profile</label>
          <select id="chat-retrieval-profile" value={settings.retrieval_profile || 'manual'} onChange={(event) => handleChange('retrieval_profile', event.target.value)} className="input-field">
            <option value="manual">Manual settings</option>
            <option value="auto">Auto by question type</option>
          </select>
        </div>
        <div>
          <label htmlFor="chat-retrieval-method" className="block text-sm font-medium mb-2">Retrieval Method</label>
          <select id="chat-retrieval-method" value={settings.retrieval_method} onChange={(event) => handleChange('retrieval_method', event.target.value)} className="input-field">
            <option value="similarity">Similarity</option>
            <option value="mmr">MMR</option>
            <option value="hybrid">Hybrid vector + keyword</option>
          </select>
        </div>
        <div>
          <label htmlFor="chat-reranker" className="block text-sm font-medium mb-2">Reranker</label>
          <select id="chat-reranker" value={settings.reranker || 'none'} onChange={(event) => handleChange('reranker', event.target.value)} className="input-field">
            <option value="none">None</option>
            <option value="enabled">Enabled</option>
          </select>
        </div>
        <label className="flex items-center">
          <input type="checkbox" checked={settings.answer_verification || false} onChange={(event) => handleChange('answer_verification', event.target.checked)} className="mr-2" />
          <span className="text-sm">Verify grounded answer</span>
        </label>
        <label className="flex items-center">
          <input type="checkbox" checked={settings.show_debug || false} onChange={(event) => handleChange('show_debug', event.target.checked)} className="mr-2" />
          <span className="text-sm">Show retrieval debug</span>
        </label>
      </div>
    </div>
  )
}
