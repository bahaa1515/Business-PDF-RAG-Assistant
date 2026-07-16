import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CookieConsentManager from './CookieConsentManager'
import { ConsentProvider, useConsent } from '../contexts/ConsentContext'
import { CONSENT_STORAGE_KEY, CONSENT_VERSION } from '../legal/storage'

function PreferencesButton() {
  const { openPreferences } = useConsent()
  return <button onClick={openPreferences}>Open preferences later</button>
}

function renderManager() {
  return render(
    <ConsentProvider>
      <CookieConsentManager />
      <PreferencesButton />
    </ConsentProvider>
  )
}

describe('CookieConsentManager', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.querySelectorAll('script[data-consent-category]').forEach((script) => script.remove())
  })

  it('defaults optional storage off and keeps necessary storage enabled', () => {
    renderManager()
    fireEvent.click(screen.getByRole('button', { name: 'Manage preferences' }))

    expect(screen.getByLabelText('Necessary storage')).toBeChecked()
    expect(screen.getByLabelText('Necessary storage')).toBeDisabled()
    expect(screen.getByLabelText('Analytics storage')).not.toBeChecked()
    expect(screen.getByLabelText('Marketing storage')).not.toBeChecked()
    expect(document.querySelector('script[data-consent-category]')).toBeNull()
  })

  it('rejects optional storage and records version and timestamp', () => {
    renderManager()
    fireEvent.click(screen.getByRole('button', { name: 'Reject optional' }))

    const stored = JSON.parse(window.localStorage.getItem(CONSENT_STORAGE_KEY))
    expect(stored).toMatchObject({
      version: CONSENT_VERSION,
      necessary: true,
      analytics: false,
      marketing: false
    })
    expect(stored.updatedAt).toBeTruthy()
    expect(document.querySelector('script[data-consent-category]')).toBeNull()
  })

  it('accepts all and allows preferences to be changed later', () => {
    renderManager()
    fireEvent.click(screen.getByRole('button', { name: 'Accept all' }))
    expect(JSON.parse(window.localStorage.getItem(CONSENT_STORAGE_KEY))).toMatchObject({
      analytics: true,
      marketing: true
    })

    fireEvent.click(screen.getByRole('button', { name: 'Open preferences later' }))
    fireEvent.click(screen.getByLabelText('Analytics storage'))
    fireEvent.click(screen.getByLabelText('Marketing storage'))
    fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }))

    expect(JSON.parse(window.localStorage.getItem(CONSENT_STORAGE_KEY))).toMatchObject({
      necessary: true,
      analytics: false,
      marketing: false
    })
  })

  it('does not load optional scripts before consent', () => {
    const appendSpy = vi.spyOn(document.head, 'appendChild')
    renderManager()
    expect(
      appendSpy.mock.calls.some(([node]) => node?.dataset?.consentCategory)
    ).toBe(false)
    appendSpy.mockRestore()
  })
})
