# Cookie And Storage Inventory

Date: 2026-06-14

DocuQuery AI currently uses browser `localStorage`. It does not currently set
browser cookies or load browser-side analytics/marketing scripts.

| Name | Type | Purpose | Necessary? | Duration | Set Before Consent? | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `docuquery_token` | `localStorage` | Stores the signed API session token used for authenticated backend requests | Yes | Until logout, browser storage is cleared, or the token expires | Yes | Demo-grade storage. Production should prefer an appropriately secured server-managed session or HttpOnly secure cookie design. |
| `docuquery_legal_acceptance.termsVersion` | Field inside `docuquery_legal_acceptance` localStorage JSON | Records the accepted Terms of Service version | Yes | Until browser storage is cleared or replaced by a newer acceptance | After login but before application use | Production requires a server-side user-level acceptance record. |
| `docuquery_legal_acceptance.privacyVersion` | Field inside `docuquery_legal_acceptance` localStorage JSON | Records the acknowledged Privacy Policy version | Yes | Until browser storage is cleared or replaced by a newer acceptance | After login but before application use | Production requires a server-side user-level acceptance record. |
| `docuquery_legal_acceptance.acceptedAt` | Field inside `docuquery_legal_acceptance` localStorage JSON | Records when the current legal versions were accepted | Yes | Until browser storage is cleared or replaced | After login but before application use | Browser timestamps are user-controlled and are not an authoritative production audit record. |
| `docuquery_storage_consent` | `localStorage` JSON | Stores consent version, timestamp, and necessary/analytics/marketing preferences | Yes | Until browser storage is cleared or the consent version changes | Yes | Necessary so the app can remember the user's storage choice. |
| Theme preference | Not used | No theme preference is currently stored | No | N/A | No | Add to this inventory before implementation. |
| Language preference | Not used | No language preference is currently stored | No | N/A | No | Add to this inventory before implementation. |
| Analytics storage | Not used | No browser analytics integration is currently installed | No | N/A | No | Disabled by default. An analytics integration must be consent-gated before being added. |
| Marketing storage | Not used | No browser marketing integration is currently installed | No | N/A | No | Disabled by default. A marketing integration must be consent-gated before being added. |
| Third-party browser scripts | Not used | No third-party analytics or marketing scripts are currently loaded in the frontend | No | N/A | No | The configured AI provider API is called server-side and is not a browser script. Its data-processing terms still require production legal review. |

## Consent Behavior

- Necessary storage is always enabled.
- Analytics and marketing preferences are disabled by default.
- Users can accept all, reject optional storage, or manage individual optional
  choices.
- Users can reopen preferences through the application footer.
- No optional scripts are installed or loaded before consent.
- Clearing browser storage clears legal acceptance and consent choices, so the
  application asks again.
- Logout removes the session token but intentionally preserves legal acceptance
  and storage preferences.

This inventory is a technical record, not legal advice.
