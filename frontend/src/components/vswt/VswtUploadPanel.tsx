import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Upload, X } from 'lucide-react'
import {
  commitVswtBatch,
  deleteVswtWeek,
  getApiErrorMessage,
  getVswtWeeks,
  uploadVswtFiles,
  type VswtUploadBatchItem,
} from '@/lib/api'
import { Button, Card, Spinner } from '@/components/ui'

const VSWT_QUERY_KEYS = ['vswt-summary', 'vswt-scorecard', 'vswt-rankings', 'vswt-leaderboards', 'vswt-trends', 'vswt-weeks']

interface DraftItem extends VswtUploadBatchItem {
  weekNumberInput: string
}

export function VswtUploadPanel() {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [draft, setDraft] = useState<DraftItem[] | null>(null)
  const [existingWeeks, setExistingWeeks] = useState<number[]>([])
  const [failedFiles, setFailedFiles] = useState<string[]>([])
  const [status, setStatus] = useState<{ type: 'ok' | 'error'; message: string } | null>(null)

  const weeksQuery = useQuery({ queryKey: ['vswt-weeks'], queryFn: () => getVswtWeeks().then(r => r.data.weeks) })

  const uploadMut = useMutation({
    mutationFn: (files: File[]) => uploadVswtFiles(files).then(r => r.data),
    onSuccess: result => {
      setStatus(null)
      setFailedFiles(result.failed_files)
      setExistingWeeks(result.existing_weeks)
      setDraft(result.batch.map(b => ({ ...b, weekNumberInput: String(b.week_number) })))
    },
    onError: err => setStatus({ type: 'error', message: getApiErrorMessage(err, 'Upload failed.') }),
  })

  const commitMut = useMutation({
    mutationFn: (items: DraftItem[]) =>
      commitVswtBatch(items.map(i => ({ filename: i.filename, week_number: Number(i.weekNumberInput), rows: i.rows }))),
    onSuccess: (_res, items) => {
      setStatus({
        type: 'ok',
        message: `Saved ${items.length} week${items.length !== 1 ? 's' : ''} — ${items.map(i => `Wk ${i.weekNumberInput}`).join(', ')}.`,
      })
      setDraft(null)
      VSWT_QUERY_KEYS.forEach(key => void qc.invalidateQueries({ queryKey: [key] }))
    },
    onError: err => setStatus({ type: 'error', message: getApiErrorMessage(err, 'Save failed.') }),
  })

  const deleteMut = useMutation({
    mutationFn: (week: number) => deleteVswtWeek(week),
    onSuccess: () => {
      VSWT_QUERY_KEYS.forEach(key => void qc.invalidateQueries({ queryKey: [key] }))
    },
  })

  function handleFiles(files: FileList | File[] | null) {
    if (!files || files.length === 0) return
    setStatus(null)
    uploadMut.mutate(Array.from(files))
  }

  function setWeekInputFor(idx: number, value: string) {
    setDraft(prev => prev?.map((d, i) => (i === idx ? { ...d, weekNumberInput: value } : d)) ?? prev)
  }

  const numbers = draft?.map(d => Number(d.weekNumberInput)) ?? []
  const dupCounts: Record<number, number> = {}
  numbers.forEach(n => { dupCounts[n] = (dupCounts[n] ?? 0) + 1 })
  const hasDupes = Object.values(dupCounts).some(c => c > 1)
  const anyInvalid = numbers.some(n => !Number.isFinite(n) || n <= 0)

  return (
    <div>
      <input
        ref={fileRef}
        type="file"
        accept=".xlsx"
        multiple
        className="hidden"
        onChange={e => handleFiles(e.target.files)}
      />
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
        className="w-full border-2 border-dashed rounded-lg p-8 transition-colors text-center mb-4"
        style={{
          borderColor: dragOver ? 'var(--ms-accent)' : 'var(--ms-border-strong)',
          backgroundColor: dragOver ? 'var(--ms-accent-light)' : 'transparent',
        }}
        disabled={uploadMut.isPending}
      >
        <div className="flex flex-col items-center gap-2" style={{ color: 'var(--ms-text-muted)' }}>
          <Upload size={28} style={{ color: 'var(--ms-accent)' }} />
          <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
            Drop this week's VSWT-WSS file(s) here, or click to browse
          </p>
          <p className="text-xs">Select as many weeks at once as you like — reads the Summary tab from each, .xlsx only</p>
        </div>
      </button>

      {uploadMut.isPending && <Spinner />}

      {status && (
        <div
          className="flex items-center gap-2 px-3.5 py-2.5 rounded-lg mb-4 text-sm"
          style={{
            backgroundColor: status.type === 'error' ? 'var(--ms-badge-alert-bg)' : 'var(--ms-badge-done-bg)',
            color: status.type === 'error' ? 'var(--ms-badge-alert-text)' : 'var(--ms-badge-done-text)',
          }}
        >
          {status.type === 'error' ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
          {status.message}
        </div>
      )}

      {failedFiles.length > 0 && (
        <p className="text-sm mb-4" style={{ color: 'var(--ms-badge-alert-text)' }}>
          {failedFiles.length} file(s) couldn't be read and were skipped: {failedFiles.join(', ')}
        </p>
      )}

      {draft && draft.length > 0 && (
        <Card className="p-4 mb-6">
          <p className="text-sm font-semibold mb-1" style={{ color: 'var(--ms-text)' }}>
            Confirm {draft.length} week{draft.length !== 1 ? 's' : ''} of data
          </p>
          <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>
            Check the week number for each file before saving — some source files mislabel this.
          </p>
          <div className="flex flex-col gap-2 mb-4">
            {draft.map((item, i) => {
              const num = Number(item.weekNumberInput)
              const dupInBatch = dupCounts[num] > 1
              const overwrite = !dupInBatch && existingWeeks.includes(num)
              return (
                <div
                  key={item.filename + i}
                  className="rounded-lg p-3"
                  style={{ border: `1px solid ${dupInBatch ? 'var(--ms-danger)' : 'var(--ms-border)'}`, backgroundColor: 'var(--ms-bg)' }}
                >
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex-1 min-w-[140px]">
                      <p className="text-xs font-semibold truncate" style={{ color: 'var(--ms-text)' }}>{item.filename}</p>
                      <p className="text-[11px] mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                        {item.shop_count} shops · detected week {item.internal_week ?? 'not found'}
                      </p>
                    </div>
                    <div>
                      <label className="block text-[10px] mb-0.5" style={{ color: 'var(--ms-text-muted)' }}>Save as week</label>
                      <input
                        type="number"
                        value={item.weekNumberInput}
                        onChange={e => setWeekInputFor(i, e.target.value)}
                        className="w-24 rounded-md px-2 py-1.5 text-sm"
                        style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
                      />
                    </div>
                  </div>
                  {(overwrite || dupInBatch) && (
                    <div className="flex gap-1.5 items-start text-xs mt-2" style={{ color: dupInBatch ? 'var(--ms-danger)' : 'var(--ms-badge-wait-text)' }}>
                      <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                      {dupInBatch
                        ? 'Duplicate week number in this batch — give each file a different week.'
                        : 'Week already exists — saving will overwrite it.'}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="secondary" onClick={() => setDraft(null)} disabled={commitMut.isPending}>Cancel</Button>
            <Button onClick={() => commitMut.mutate(draft)} disabled={hasDupes || anyInvalid || commitMut.isPending}>
              {commitMut.isPending ? 'Saving…' : `Save ${draft.length} week${draft.length !== 1 ? 's' : ''}`}
            </Button>
          </div>
        </Card>
      )}

      <p className="text-sm font-semibold mb-2" style={{ color: 'var(--ms-text)' }}>
        Weeks loaded {weeksQuery.data ? `(${weeksQuery.data.length})` : ''}
      </p>
      {weeksQuery.isLoading ? (
        <Spinner />
      ) : (
        <div className="flex flex-col gap-1.5">
          {(weeksQuery.data ?? []).map(w => (
            <div
              key={w.week}
              className="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
            >
              <span className="font-bold w-14" style={{ color: 'var(--ms-text)' }}>{w.week}</span>
              <span className="w-24" style={{ color: 'var(--ms-text-muted)' }}>{w.shop_count} shops</span>
              <span className="flex-1 text-xs truncate" style={{ color: 'var(--ms-text-muted)' }}>
                {w.source_filenames.join(', ')}
              </span>
              <button
                onClick={() => {
                  if (window.confirm(`Remove week ${w.week}? This deletes ${w.shop_count} shop rows for every shop, not just yours.`)) {
                    deleteMut.mutate(w.week)
                  }
                }}
                disabled={deleteMut.isPending}
                className="flex items-center gap-1 rounded-md px-2 py-1 text-xs"
                style={{ border: '1px solid var(--ms-border)', color: 'var(--ms-text-muted)' }}
              >
                <X size={12} /> Remove
              </button>
            </div>
          ))}
          {weeksQuery.data?.length === 0 && (
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>No weeks uploaded yet.</p>
          )}
        </div>
      )}
    </div>
  )
}
