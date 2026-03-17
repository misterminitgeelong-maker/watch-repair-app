import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, ScanLine } from 'lucide-react'
import { completeStocktake, getApiErrorMessage, getStocktake, saveStocktakeLines, type StocktakeLine } from '@/lib/api'
import { varianceTone } from '@/lib/stocktake'
import { Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { formatCents } from '@/lib/utils'

type DraftEntry = {
  stock_item_id: string
  counted_qty: string
}

const ROW_TONES: Record<string, { border: string; background: string; label: string; text: string }> = {
  neutral: { border: 'var(--cafe-border)', background: 'var(--cafe-surface)', label: 'Pending', text: 'var(--cafe-text-muted)' },
  match: { border: '#B8D8BF', background: '#EFF8F0', label: 'Matched', text: '#24543B' },
  shortage: { border: '#E9C0C0', background: '#FCF1F1', label: 'Shortage', text: '#8B3A3A' },
  over: { border: '#F1D2A7', background: '#FFF5E7', label: 'Over', text: '#9B6820' },
}

export default function StocktakeWorkspacePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [groupCode, setGroupCode] = useState('')
  const [hideZeroStock, setHideZeroStock] = useState(false)
  const [hideCounted, setHideCounted] = useState(true)
  const [countQueueMode, setCountQueueMode] = useState(true)
  const [draftEntries, setDraftEntries] = useState<Record<string, DraftEntry>>({})
  const [saveStatus, setSaveStatus] = useState('')
  const rowInputRefs = useRef<Record<string, HTMLInputElement | null>>({})

  const effectiveHideCounted = hideCounted || countQueueMode

  const { data: stocktake, isLoading } = useQuery({
    queryKey: ['stocktake', id, search, groupCode, hideZeroStock, effectiveHideCounted],
    queryFn: () => getStocktake(id!, {
      search: search.trim() || undefined,
      group_code: groupCode || undefined,
      hide_zero_stock: hideZeroStock,
      hide_counted: effectiveHideCounted,
    }).then(r => r.data),
    enabled: !!id,
  })

  const saveMut = useMutation({
    mutationFn: (entries: DraftEntry[]) => saveStocktakeLines(id!, entries.map(entry => ({
      stock_item_id: entry.stock_item_id,
      counted_qty: Number(entry.counted_qty),
    }))),
    onSuccess: (_response, entries) => {
      setDraftEntries(current => {
        const next = { ...current }
        for (const entry of entries) {
          if (next[entry.stock_item_id]?.counted_qty === entry.counted_qty) delete next[entry.stock_item_id]
        }
        return next
      })
      setSaveStatus(`Saved ${entries.length} line${entries.length === 1 ? '' : 's'} at ${new Date().toLocaleTimeString()}`)
      qc.invalidateQueries({ queryKey: ['stocktake', id] })
      qc.invalidateQueries({ queryKey: ['stocktakes'] })
    },
    onError: err => setSaveStatus(getApiErrorMessage(err, 'Autosave failed.')),
  })

  const completeMut = useMutation({
    mutationFn: () => completeStocktake(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stocktake', id] })
      qc.invalidateQueries({ queryKey: ['stocktakes'] })
      navigate(`/stocktakes/${id}/summary`)
    },
    onError: err => setSaveStatus(getApiErrorMessage(err, 'Failed to complete stocktake.')),
  })

  useEffect(() => {
    const pending = Object.values(draftEntries).filter(entry => entry.counted_qty !== '' && !Number.isNaN(Number(entry.counted_qty)))
    if (pending.length === 0 || !id) return undefined
    setSaveStatus('Saving…')
    const timer = window.setTimeout(() => {
      saveMut.mutate(pending)
    }, 700)
    return () => window.clearTimeout(timer)
  }, [draftEntries, id])

  const progress = stocktake?.progress ?? { counted_items: 0, total_items: 0 }

  function lineCountedValue(line: StocktakeLine) {
    const pending = draftEntries[line.stock_item_id]
    if (pending) return pending.counted_qty
    return line.counted_qty == null ? '' : String(line.counted_qty)
  }

  function isLineCounted(line: StocktakeLine) {
    return lineCountedValue(line).trim() !== ''
  }

  function lineVariance(line: StocktakeLine) {
    const currentValue = lineCountedValue(line)
    if (!currentValue.trim()) return null
    const counted = Number(currentValue)
    if (Number.isNaN(counted)) return null
    return counted - line.expected_qty
  }

  const visibleLines = useMemo(() => {
    const lines = [...(stocktake?.lines ?? [])]
    if (!countQueueMode) return lines
    return lines.sort((left, right) => {
      const leftCounted = isLineCounted(left)
      const rightCounted = isLineCounted(right)
      if (leftCounted !== rightCounted) return leftCounted ? 1 : -1
      return left.item_code.localeCompare(right.item_code)
    })
  }, [countQueueMode, draftEntries, stocktake])

  const remainingLines = useMemo(
    () => visibleLines.filter(line => !isLineCounted(line)),
    [visibleLines, draftEntries]
  )

  const varianceLines = useMemo(
    () => visibleLines.filter(line => {
      const variance = lineVariance(line)
      return variance != null && variance !== 0
    }),
    [visibleLines, draftEntries]
  )

  function focusNext(currentIndex: number) {
    const remainingAfterCurrent = visibleLines.slice(currentIndex + 1).find(line => !isLineCounted(line))
    const nextLine = remainingAfterCurrent ?? visibleLines[currentIndex + 1] ?? remainingLines[0]
    if (!nextLine) return
    window.requestAnimationFrame(() => {
      rowInputRefs.current[nextLine.id]?.focus()
      rowInputRefs.current[nextLine.id]?.select()
    })
  }

  function focusSearchMatch() {
    const token = search.trim().toLowerCase()
    if (!token) return
    const exactCodeMatch = visibleLines.find(line => line.item_code.toLowerCase() === token)
    const match = exactCodeMatch ?? visibleLines.find(line => {
      const haystack = `${line.item_code} ${line.full_description ?? ''} ${line.item_description ?? ''}`.toLowerCase()
      return haystack.includes(token)
    })
    if (!match) return
    rowInputRefs.current[match.id]?.focus()
    rowInputRefs.current[match.id]?.select()
  }

  function focusNextRemaining() {
    const nextLine = remainingLines[0] ?? visibleLines[0]
    if (!nextLine) return
    rowInputRefs.current[nextLine.id]?.focus()
    rowInputRefs.current[nextLine.id]?.select()
  }

  if (isLoading) return <Spinner />
  if (!stocktake) return <EmptyState message="Stocktake session not found." />

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Link
          to="/stocktakes"
          className="inline-flex items-center gap-1 text-sm font-medium"
          style={{ color: 'var(--cafe-text-muted)' }}
        >
          <ChevronLeft size={14} /> Back to stocktakes
        </Link>
        <div className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>{saveStatus || 'Autosave ready'}</div>
      </div>

      <PageHeader
        title={stocktake.name}
        action={(
          <div className="flex flex-wrap gap-2">
            <Link to={`/stocktakes/${stocktake.id}/summary`}>
              <Button variant="secondary">View summary</Button>
            </Link>
            <Button onClick={() => completeMut.mutate()} disabled={completeMut.isPending || progress.total_items === 0}>
              {completeMut.isPending ? 'Completing…' : 'Complete stocktake'}
            </Button>
          </div>
        )}
      />

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        <div className="sticky top-0 z-30 bg-[var(--cafe-surface)] p-3 rounded-2xl shadow-sm xl:col-span-3 flex flex-col gap-3">
          <div className="flex flex-wrap gap-3 items-center">
            <Select
              label="Group"
              value={groupCode}
              onChange={event => setGroupCode(event.target.value)}
              style={{ minWidth: 120, maxWidth: 220 }}
            >
              <option value="">All groups</option>
              {Array.from(new Set((stocktake.lines ?? []).map(line => line.group_code).filter(Boolean))).sort().map(code => (
                <option key={code} value={code}>{code} / {stocktake.lines.find(line => line.group_code === code)?.group_name ?? code}</option>
              ))}
            </Select>
            <Button variant="ghost" onClick={() => setGroupCode('')} disabled={!groupCode}>
              All groups
            </Button>
            <Input
              label="Search item"
              value={search}
              onChange={event => setSearch(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  focusSearchMatch()
                }
              }}
              placeholder="Item code or description"
              style={{ minWidth: 120, maxWidth: 220 }}
            />
            <Button variant="ghost" onClick={() => setSearch('')} disabled={!search.trim()}>
              Clear search
            </Button>
          </div>
          <div className="flex flex-wrap gap-3 items-center mt-2">
            <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
              <input type="checkbox" checked={hideZeroStock} onChange={event => setHideZeroStock(event.target.checked)} /> Hide zero-stock
            </label>
            <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
              <input
                type="checkbox"
                checked={countQueueMode}
                onChange={event => setCountQueueMode(event.target.checked)}
              /> Count queue mode
            </label>
            <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
              <input
                type="checkbox"
                checked={hideCounted}
                disabled={countQueueMode}
                onChange={event => setHideCounted(event.target.checked)}
              /> Hide counted {countQueueMode ? '(on automatically in queue mode)' : ''}
            </label>
            <Button variant="secondary" onClick={focusNextRemaining} disabled={visibleLines.length === 0}>
              Jump to next needing count
            </Button>
          </div>
        </div>

        <Card className="p-4">
          <div className="text-xs uppercase tracking-wide font-semibold" style={{ color: 'var(--cafe-text-muted)' }}>Progress</div>
          <div className="mt-2 text-3xl font-semibold" style={{ color: 'var(--cafe-text)' }}>
            {progress.counted_items} / {progress.total_items}
          </div>
          <div className="mt-3 h-2 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--cafe-bg)' }}>
            <div
              className="h-full rounded-full"
              style={{
                width: progress.total_items === 0 ? '0%' : `${Math.round((progress.counted_items / progress.total_items) * 100)}%`,
                backgroundColor: 'var(--cafe-amber)',
              }}
            />
          </div>
          <div className="mt-3 space-y-2 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
            <div className="flex items-center gap-2">
              <ScanLine size={15} /> Queue mode keeps the list focused on items still needing a count.
            </div>
            <div>{remainingLines.length} remaining to count</div>
            <div>{varianceLines.length} counted lines currently showing a variance</div>
            <div>Enter saves and jumps forward. Shift+Enter keeps focus on the same line.</div>
          </div>
        </Card>
      </div>

      {visibleLines.length === 0 ? (
        <EmptyState message="No lines match the current filters." />
      ) : (
        <div className="space-y-2">
          {visibleLines.map((line, index) => {
            const currentValue = lineCountedValue(line)
            const variance = lineVariance(line)
            const tone = ROW_TONES[varianceTone(variance)]
            return (
              <Card
                key={line.id}
                className="p-2 sm:p-3 md:p-4"
                style={{ borderColor: tone.border, backgroundColor: tone.background }}
              >
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2 md:gap-3 items-center">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-base font-semibold" style={{ color: 'var(--cafe-text)' }}>{line.item_code}</span>
                      <span className="text-xs px-2 py-1 rounded-full" style={{ backgroundColor: '#F5EDE0', color: 'var(--cafe-text-mid)' }}>
                        {line.group_code}{line.group_name ? ` / ${line.group_name}` : ''}
                      </span>
                      <span className="text-xs font-semibold" style={{ color: tone.text }}>{tone.label}</span>
                    </div>
                    <div className="mt-1 text-sm" style={{ color: 'var(--cafe-text)' }}>{line.full_description || line.item_description || 'No description'}</div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <div className="text-xs uppercase tracking-wide font-semibold" style={{ color: 'var(--cafe-text-muted)' }}>System qty</div>
                    <div className="mt-1 text-xl font-semibold" style={{ color: 'var(--cafe-text)' }}>{line.expected_qty}</div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <Input
                      label="Counted qty"
                      type="number"
                      min="0"
                      step="0.01"
                      value={currentValue}
                      ref={element => {
                        rowInputRefs.current[line.id] = element
                      }}
                      onChange={event => {
                        setDraftEntries(current => ({
                          ...current,
                          [line.stock_item_id]: {
                            stock_item_id: line.stock_item_id,
                            counted_qty: event.target.value,
                          },
                        }))
                      }}
                      onFocus={event => event.target.select()}
                      onKeyDown={event => {
                        if (event.key === 'Enter') {
                          event.preventDefault()
                          if (event.shiftKey) return
                          focusNext(index)
                        }
                      }}
                      style={{ fontSize: '1.25rem', height: '3.2rem', padding: '0.5rem 1rem' }}
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <div className="text-xs uppercase tracking-wide font-semibold" style={{ color: 'var(--cafe-text-muted)' }}>Variance</div>
                    <div className="mt-1 text-xl font-semibold" style={{ color: tone.text }}>
                      {variance == null ? 'Pending' : `${variance > 0 ? '+' : ''}${variance}`}
                    </div>
                    <div className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
                      {variance == null ? 'No count yet' : formatCents(Math.round(variance * line.cost_price_cents))}
                    </div>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}