import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useIntakeDraft } from './useIntakeDraft'
import { draftScope, draftStorageKey, loadDraft, saveDraft } from '@/lib/draftStorage'
import DraftRestoredNotice from '@/components/DraftRestoredNotice'

type Form = { title: string; notes: string }

const KIND = 'watch-intake'
const SCOPE = draftScope('tenant-1', 'user-1')

function renderDraftHook(initial: Form, overrides: Partial<Parameters<typeof useIntakeDraft<Form>>[0]> = {}) {
  const onRestore = vi.fn()
  const view = renderHook(
    ({ value }: { value: Form }) =>
      useIntakeDraft<Form>({
        kind: KIND,
        scope: SCOPE,
        value,
        hasContent: v => Boolean(v.title.trim() || v.notes.trim()),
        onRestore,
        debounceMs: 0,
        ...overrides,
      }),
    { initialProps: { value: initial } },
  )
  return { ...view, onRestore }
}

describe('useIntakeDraft', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('autosaves once the form has content', async () => {
    const { rerender } = renderDraftHook({ title: '', notes: '' })
    // An empty form is not worth a draft.
    expect(loadDraft(KIND, SCOPE)).toBeNull()

    rerender({ value: { title: 'Battery swap', notes: '' } })
    await waitFor(() => {
      expect(loadDraft<Form>(KIND, SCOPE)?.data.title).toBe('Battery swap')
    })
  })

  it('restores an existing draft on mount and reports when it was saved', async () => {
    const savedAt = Date.now() - 120_000
    saveDraft(KIND, SCOPE, { title: 'Half-typed', notes: 'x' }, savedAt)

    const { result, onRestore } = renderDraftHook({ title: '', notes: '' })
    await waitFor(() => expect(onRestore).toHaveBeenCalledTimes(1))
    expect(onRestore).toHaveBeenCalledWith({ title: 'Half-typed', notes: 'x' })
    expect(result.current.restoredAt).toBe(savedAt)
  })

  it('does not restore a draft belonging to another shop/user', async () => {
    saveDraft(KIND, draftScope('tenant-2', 'user-9'), { title: 'Other shop', notes: '' })
    const { result, onRestore } = renderDraftHook({ title: '', notes: '' })
    await act(async () => {})
    expect(onRestore).not.toHaveBeenCalled()
    expect(result.current.restoredAt).toBeNull()
  })

  it('does not save while disabled (submitting or already created)', async () => {
    const { rerender } = renderDraftHook({ title: '', notes: '' }, { enabled: false })
    rerender({ value: { title: 'Should not persist', notes: '' } })
    await act(async () => {})
    expect(loadDraft(KIND, SCOPE)).toBeNull()
  })

  it('clearSavedDraft removes the draft and stops further saves', async () => {
    const { result, rerender } = renderDraftHook({ title: 'Typed', notes: '' })
    await waitFor(() => expect(loadDraft(KIND, SCOPE)).not.toBeNull())

    act(() => result.current.clearSavedDraft())
    expect(loadDraft(KIND, SCOPE)).toBeNull()
    expect(result.current.restoredAt).toBeNull()

    rerender({ value: { title: 'More typing after success', notes: '' } })
    await act(async () => {})
    expect(loadDraft(KIND, SCOPE)).toBeNull()
  })

  it('discardDraft clears storage but keeps protecting later edits', async () => {
    const { result, rerender } = renderDraftHook({ title: 'Typed', notes: '' })
    await waitFor(() => expect(loadDraft(KIND, SCOPE)).not.toBeNull())

    act(() => result.current.discardDraft())
    expect(localStorage.getItem(draftStorageKey(KIND, SCOPE))).toBeNull()
    expect(result.current.restoredAt).toBeNull()

    rerender({ value: { title: 'Fresh start', notes: '' } })
    await waitFor(() => {
      expect(loadDraft<Form>(KIND, SCOPE)?.data.title).toBe('Fresh start')
    })
  })

  it('dismissNotice hides the notice without touching the draft', async () => {
    saveDraft(KIND, SCOPE, { title: 'Half-typed', notes: '' })
    const { result } = renderDraftHook({ title: '', notes: '' })
    await waitFor(() => expect(result.current.restoredAt).not.toBeNull())

    act(() => result.current.dismissNotice())
    expect(result.current.restoredAt).toBeNull()
    expect(loadDraft(KIND, SCOPE)).not.toBeNull()
  })

  it('flushes the draft when the tab is backgrounded', async () => {
    const { rerender } = renderDraftHook({ title: '', notes: '' }, { debounceMs: 100_000 })
    rerender({ value: { title: 'Backgrounded mid-typing', notes: '' } })
    expect(loadDraft(KIND, SCOPE)).toBeNull()

    act(() => {
      Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
    })
    expect(loadDraft<Form>(KIND, SCOPE)?.data.title).toBe('Backgrounded mid-typing')
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  })

  it('does nothing when there is no signed-in scope', async () => {
    const { rerender } = renderDraftHook({ title: '', notes: '' }, { scope: null })
    rerender({ value: { title: 'No scope', notes: '' } })
    await act(async () => {})
    expect(localStorage.length).toBe(0)
  })
})

describe('DraftRestoredNotice', () => {
  it('announces the restore and offers a discard action', async () => {
    const user = userEvent.setup()
    const onDiscard = vi.fn()
    render(<DraftRestoredNotice savedAt={Date.now() - 120_000} onDiscard={onDiscard} />)

    const notice = screen.getByRole('status')
    expect(notice).toHaveAttribute('aria-live', 'polite')
    expect(notice).toHaveTextContent(/draft restored/i)
    expect(notice).toHaveTextContent(/2 minutes ago/)

    await user.click(screen.getByRole('button', { name: /discard draft/i }))
    expect(onDiscard).toHaveBeenCalledTimes(1)
  })

  it('tells the user photos must be reselected', () => {
    render(<DraftRestoredNotice savedAt={Date.now()} onDiscard={() => {}} photosNeedReselect photoCount={2} />)
    expect(screen.getByRole('status')).toHaveTextContent(/2 photos were attached before/i)
  })

  it('renders nothing when no draft was restored', () => {
    const { container } = render(<DraftRestoredNotice savedAt={null} onDiscard={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })
})
