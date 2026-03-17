import { useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { FileSpreadsheet, PlayCircle, RefreshCw, Search, Upload } from 'lucide-react'
import {
  createStocktake,
  getApiErrorMessage,
  importStockFile,
  listStockItems,
  listStocktakes,
  type StockImportSummaryResponse,
} from '@/lib/api'
import { STOCK_GROUP_OPTIONS } from '@/lib/stocktake'
import { Button, Card, EmptyState, Input, PageHeader, Select, Spinner, Textarea } from '@/components/ui'
import { formatDate } from '@/lib/utils'

export default function StocktakesPage() {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [importResult, setImportResult] = useState<StockImportSummaryResponse | null>(null)
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    name: '',
    group_code: '',
    search: '',
    hide_zero_stock: false,
    notes: '',
  })

  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ['stocktakes'],
    queryFn: () => listStocktakes().then(r => r.data),
  })

  const { data: stockItems = [] } = useQuery({
    queryKey: ['stock-items-summary'],
    queryFn: () => listStockItems().then(r => r.data),
  })

  const inventoryStats = useMemo(() => {
    const groups = new Set(stockItems.map(item => item.group_code).filter(Boolean))
    const zeroStock = stockItems.filter(item => item.system_stock_qty === 0).length
    return { totalItems: stockItems.length, groups: groups.size, zeroStock }
  }, [stockItems])

  const importMut = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Select a stock master file first.')
      return importStockFile(file)
    },
    onSuccess: ({ data }) => {
      setImportResult(data)
      setError('')
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      qc.invalidateQueries({ queryKey: ['stock-items-summary'] })
      qc.invalidateQueries({ queryKey: ['stock-items'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Stock import failed.')),
  })

  const createMut = useMutation({
    mutationFn: () => createStocktake({
      name: form.name.trim(),
      group_code: form.group_code || undefined,
      search: form.search.trim() || undefined,
      hide_zero_stock: form.hide_zero_stock,
      notes: form.notes.trim() || undefined,
    }),
    onSuccess: () => {
      setError('')
      setForm({ name: '', group_code: '', search: '', hide_zero_stock: false, notes: '' })
      qc.invalidateQueries({ queryKey: ['stocktakes'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to create stocktake.')),
  })

  if (isLoading) return <Spinner />

  return (
    <div className="space-y-6">
      <PageHeader title="Stocktake" />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <Card className="p-5 xl:col-span-2">
          <div className="flex items-start gap-3 mb-4">
            <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ backgroundColor: '#EEE6DA' }}>
              <FileSpreadsheet size={20} style={{ color: 'var(--cafe-gold-dark)' }} />
            </div>
            <div>
              <h2 className="text-base font-semibold" style={{ color: 'var(--cafe-text)' }}>Import stock master</h2>
              <p className="text-sm mt-1" style={{ color: 'var(--cafe-text-muted)' }}>
                Upload the shop stock export. The importer prefers DATA for item master fields and SUMMARY for stock values, then merges by item code.
              </p>
            </div>
          </div>

          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,.xls,.xlsm,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={event => {
              const selected = event.target.files?.[0] ?? null
              setFile(selected)
              setImportResult(null)
              setError('')
            }}
          />

          <button
            onClick={() => fileRef.current?.click()}
            className="w-full rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors"
            style={{ borderColor: 'var(--cafe-border-2)' }}
          >
            <div className="flex flex-col items-center gap-2">
              <Upload size={30} style={{ color: 'var(--cafe-amber)' }} />
              <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{file ? file.name : 'Select a CSV or Excel stock file'}</p>
              <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                {file ? `${(file.size / 1024).toFixed(1)} KB` : 'Supports CSV, XLSX, XLS, XLSM'}
              </p>
            </div>
          </button>

          <div className="mt-4 flex flex-wrap gap-3 items-center justify-between">
            <div className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
              Current catalogue: <strong style={{ color: 'var(--cafe-text)' }}>{inventoryStats.totalItems}</strong> items across{' '}
              <strong style={{ color: 'var(--cafe-text)' }}>{inventoryStats.groups}</strong> groups.
            </div>
            <Button onClick={() => importMut.mutate()} disabled={!file || importMut.isPending}>
              <Upload size={15} />
              {importMut.isPending ? 'Importing…' : 'Import stock'}
            </Button>
          </div>

          {importResult && (
            <div className="mt-4 rounded-xl p-4" style={{ backgroundColor: '#EDF6EF', border: '1px solid #C9E7D1' }}>
              <p className="text-sm font-semibold" style={{ color: '#24543B' }}>Stock import complete</p>
              <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div><span style={{ color: '#3A6B53' }}>Imported</span><br /><strong>{importResult.imported}</strong></div>
                <div><span style={{ color: '#3A6B53' }}>Created</span><br /><strong>{importResult.created}</strong></div>
                <div><span style={{ color: '#3A6B53' }}>Updated</span><br /><strong>{importResult.updated}</strong></div>
                <div><span style={{ color: '#3A6B53' }}>Sheets</span><br /><strong>{importResult.sheet_names.join(', ') || 'DATA'}</strong></div>
              </div>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="text-base font-semibold mb-4" style={{ color: 'var(--cafe-text)' }}>New stocktake session</h2>
          <div className="space-y-3">
            <Input
              label="Session name"
              value={form.name}
              onChange={event => setForm(current => ({ ...current, name: event.target.value }))}
              placeholder="March full stocktake"
            />
            <Select
              label="Group filter"
              value={form.group_code}
              onChange={event => setForm(current => ({ ...current, group_code: event.target.value }))}
            >
              <option value="">All stock</option>
              {STOCK_GROUP_OPTIONS.map(option => (
                <option key={option.code} value={option.code}>{option.code} / {option.name}</option>
              ))}
            </Select>
            <Input
              label="Search scope"
              value={form.search}
              onChange={event => setForm(current => ({ ...current, search: event.target.value }))}
              placeholder="Item code or description"
            />
            <label className="flex items-start gap-2 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
              <input
                type="checkbox"
                checked={form.hide_zero_stock}
                onChange={event => setForm(current => ({ ...current, hide_zero_stock: event.target.checked }))}
              />
              <span>Exclude zero-stock items from the initial count list</span>
            </label>
            <Textarea
              label="Notes"
              value={form.notes}
              onChange={event => setForm(current => ({ ...current, notes: event.target.value }))}
              rows={3}
            />
            <Button
              onClick={() => createMut.mutate()}
              disabled={!form.name.trim() || createMut.isPending || inventoryStats.totalItems === 0}
              className="w-full"
            >
              <PlayCircle size={16} />
              {createMut.isPending ? 'Creating…' : 'Start stocktake'}
            </Button>
          </div>
        </Card>
      </div>

      {error && (
        <Card className="p-4" style={{ borderColor: '#EBC1C1', backgroundColor: '#FDF1F1' }}>
          <p className="text-sm" style={{ color: '#8B3A3A' }}>{error}</p>
        </Card>
      )}

      <Card>
        <div className="px-5 py-4 flex items-center justify-between gap-3" style={{ borderBottom: '1px solid var(--cafe-border)' }}>
          <div>
            <h2 className="font-semibold" style={{ color: 'var(--cafe-text)' }}>Sessions</h2>
            <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>Resume unfinished counts or open completed summaries.</p>
          </div>
          <Button variant="secondary" onClick={() => qc.invalidateQueries({ queryKey: ['stocktakes'] })}>
            <RefreshCw size={15} /> Refresh
          </Button>
        </div>

        {sessions.length === 0 ? (
          <EmptyState message="No stocktake sessions yet." />
        ) : (
          <div className="divide-y" style={{ borderColor: 'var(--cafe-border)' }}>
            {sessions.map(session => (
              <div key={session.id} className="px-5 py-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                <div>
                  <p className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{session.name}</p>
                  <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
                    {session.group_code_filter ? `${session.group_code_filter} only` : 'All groups'} · {session.progress.counted_items} / {session.progress.total_items} counted · Created {formatDate(session.created_at)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link to={`/stocktakes/${session.id}`}>
                    <Button variant="secondary">
                      <Search size={15} /> Open workspace
                    </Button>
                  </Link>
                  <Link to={`/stocktakes/${session.id}/summary`}>
                    <Button>Summary</Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}