import { beforeEach, describe, expect, it } from 'vitest'
import {
  DRAFT_SCHEMA_VERSION,
  DRAFT_TTL_MS,
  clearDraft,
  clearExpiredDrafts,
  describeDraftAge,
  draftScope,
  draftStorageKey,
  loadDraft,
  photoMetaFromFile,
  sanitizeDraftValue,
  saveDraft,
} from './draftStorage'

const KIND = 'watch-intake'
const SCOPE = draftScope('tenant-1', 'user-1')

describe('draftStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('round-trips a draft within its scope', () => {
    expect(saveDraft(KIND, SCOPE, { title: 'Battery swap', step: 3 })).toBe(true)
    expect(loadDraft<{ title: string; step: number }>(KIND, SCOPE)).toEqual({
      data: { title: 'Battery swap', step: 3 },
      savedAt: expect.any(Number),
    })
  })

  it('keeps drafts of different shops/users apart', () => {
    saveDraft(KIND, SCOPE, { title: 'Shop one' })
    const otherScope = draftScope('tenant-2', 'user-1')
    expect(loadDraft(KIND, otherScope)).toBeNull()
    expect(loadDraft(KIND, SCOPE)).not.toBeNull()
  })

  it('keeps drafts of different intake types apart', () => {
    saveDraft('watch-intake', SCOPE, { title: 'watch' })
    saveDraft('shoe-intake', SCOPE, { title: 'shoe' })
    expect(loadDraft<{ title: string }>('watch-intake', SCOPE)?.data.title).toBe('watch')
    expect(loadDraft<{ title: string }>('shoe-intake', SCOPE)?.data.title).toBe('shoe')
  })

  it('drops drafts past the TTL', () => {
    const now = 1_700_000_000_000
    saveDraft(KIND, SCOPE, { title: 'stale' }, now)
    expect(loadDraft(KIND, SCOPE, { now: now + DRAFT_TTL_MS - 1 })).not.toBeNull()

    saveDraft(KIND, SCOPE, { title: 'stale' }, now)
    expect(loadDraft(KIND, SCOPE, { now: now + DRAFT_TTL_MS + 1 })).toBeNull()
    // The expired entry is removed, not left behind to be re-read.
    expect(localStorage.getItem(draftStorageKey(KIND, SCOPE))).toBeNull()
  })

  it('ignores an incompatible schema version', () => {
    const key = draftStorageKey(KIND, SCOPE)
    localStorage.setItem(
      key,
      JSON.stringify({ v: DRAFT_SCHEMA_VERSION + 1, kind: KIND, scope: SCOPE, savedAt: Date.now(), data: { a: 1 } }),
    )
    expect(loadDraft(KIND, SCOPE)).toBeNull()
  })

  it('ignores corrupt JSON without throwing', () => {
    localStorage.setItem(draftStorageKey(KIND, SCOPE), '{not json')
    expect(loadDraft(KIND, SCOPE)).toBeNull()
    expect(localStorage.getItem(draftStorageKey(KIND, SCOPE))).toBeNull()
  })

  it('ignores an envelope whose kind/scope was tampered with', () => {
    localStorage.setItem(
      draftStorageKey(KIND, SCOPE),
      JSON.stringify({ v: DRAFT_SCHEMA_VERSION, kind: 'other', scope: SCOPE, savedAt: Date.now(), data: { a: 1 } }),
    )
    expect(loadDraft(KIND, SCOPE)).toBeNull()
  })

  it('clearDraft removes only the matching draft', () => {
    saveDraft('watch-intake', SCOPE, { a: 1 })
    saveDraft('shoe-intake', SCOPE, { a: 2 })
    clearDraft('watch-intake', SCOPE)
    expect(loadDraft('watch-intake', SCOPE)).toBeNull()
    expect(loadDraft('shoe-intake', SCOPE)).not.toBeNull()
  })

  it('sweeps expired and legacy-version drafts', () => {
    const now = 1_700_000_000_000
    saveDraft('watch-intake', SCOPE, { a: 1 }, now - DRAFT_TTL_MS - 1)
    saveDraft('shoe-intake', SCOPE, { a: 2 }, now)
    localStorage.setItem('mainspring.draft.v0.legacy.scope', JSON.stringify({ v: 0 }))
    localStorage.setItem('unrelated-key', 'keep me')

    expect(clearExpiredDrafts(now)).toBe(2)
    expect(loadDraft('shoe-intake', SCOPE, { now })).not.toBeNull()
    expect(localStorage.getItem('mainspring.draft.v0.legacy.scope')).toBeNull()
    expect(localStorage.getItem('unrelated-key')).toBe('keep me')
  })

  describe('sanitizeDraftValue', () => {
    it('strips File and Blob values instead of storing them', () => {
      const file = new File(['x'], 'front.jpg', { type: 'image/jpeg' })
      const clean = sanitizeDraftValue({ title: 'Job', front: file, notes: 'ok' }) as Record<string, unknown>
      expect(clean).toEqual({ title: 'Job', notes: 'ok' })
      expect('front' in clean).toBe(false)
    })

    it('strips functions, symbols and undefined', () => {
      const clean = sanitizeDraftValue({ a: 1, b: () => 1, c: undefined, d: Symbol('s'), e: 'keep' })
      expect(clean).toEqual({ a: 1, e: 'keep' })
    })

    it('keeps nested structures and normalises dates', () => {
      const clean = sanitizeDraftValue({
        watches: [{ brand: 'Rolex', photo: new File([''], 'a.jpg') }],
        when: new Date('2026-01-02T03:04:05.000Z'),
      })
      expect(clean).toEqual({
        watches: [{ brand: 'Rolex' }],
        when: '2026-01-02T03:04:05.000Z',
      })
    })

    it('replaces non-finite numbers rather than writing null-ish JSON', () => {
      expect(sanitizeDraftValue({ n: Number.NaN, m: 4 })).toEqual({ m: 4 })
    })

    it('survives a round-trip through saveDraft with a File in the payload', () => {
      const file = new File(['x'], 'back.jpg', { type: 'image/jpeg' })
      saveDraft(KIND, SCOPE, { title: 'T', photo: file, photoMeta: photoMetaFromFile(file) })
      const loaded = loadDraft<{ title: string; photo?: unknown; photoMeta: { name: string } }>(KIND, SCOPE)
      expect(loaded?.data.photo).toBeUndefined()
      expect(loaded?.data.photoMeta.name).toBe('back.jpg')
    })
  })

  describe('describeDraftAge', () => {
    it('formats recent and older drafts', () => {
      const now = 1_700_000_000_000
      expect(describeDraftAge(now - 5_000, now)).toBe('just now')
      expect(describeDraftAge(now - 60_000, now)).toBe('1 minute ago')
      expect(describeDraftAge(now - 12 * 60_000, now)).toBe('12 minutes ago')
      expect(describeDraftAge(now - 60 * 60_000, now)).toBe('1 hour ago')
      expect(describeDraftAge(now - 3 * 60 * 60_000, now)).toBe('3 hours ago')
    })
  })
})
