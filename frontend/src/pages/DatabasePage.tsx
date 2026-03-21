import { useState, useRef } from 'react'
import { Upload, CheckCircle, AlertCircle, FileSpreadsheet, Search, Wrench, Cpu } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { importCsv, listWatchCatalogueGroups, searchWatchCatalogueItems, listWatchMovements, type CsvImportResult } from '@/lib/api'
import { PageHeader, Card, Button } from '@/components/ui'

function WatchCatalogueTab() {
  const [repairSearch, setRepairSearch] = useState('')
  const [repairGroup, setRepairGroup] = useState('')
  const [movementSearch, setMovementSearch] = useState('')

  const { data: groups = [] } = useQuery({
    queryKey: ['watch-catalogue-groups'],
    queryFn: () => listWatchCatalogueGroups().then(r => r.data),
  })
  const { data: repairItems = [] } = useQuery({
    queryKey: ['watch-catalogue-items', repairSearch, repairGroup],
    queryFn: () => searchWatchCatalogueItems({ q: repairSearch || undefined, group: repairGroup || undefined }).then(r => r.data),
  })
  const { data: movementsData } = useQuery({
    queryKey: ['watch-movements'],
    queryFn: () => listWatchMovements().then(r => r.data),
  })

  const movements = movementsData?.movements ?? []
  const q = movementSearch.trim().toLowerCase()
  const filteredMovements = q
    ? movements.filter(m => m.name.toLowerCase().includes(q) || (m.key ?? '').toLowerCase().includes(q))
    : movements

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Wrench size={20} style={{ color: 'var(--cafe-amber)' }} />
          <h2 className="text-base font-semibold" style={{ color: 'var(--cafe-text)' }}>Repair Services</h2>
        </div>
        <div className="flex gap-2 mb-3">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--cafe-text-muted)' }} />
            <input
              type="text"
              placeholder="Search repairs…"
              value={repairSearch}
              onChange={e => setRepairSearch(e.target.value)}
              className="w-full h-9 rounded-lg border pl-8 pr-3 text-sm outline-none focus:ring-2"
              style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            />
          </div>
          <select
            value={repairGroup}
            onChange={e => setRepairGroup(e.target.value)}
            className="h-9 rounded-lg border px-2 text-sm"
            style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
          >
            <option value="">All categories</option>
            {groups.map(g => <option key={g.id} value={g.id}>{g.label}</option>)}
          </select>
        </div>
        <div className="rounded-lg border overflow-y-auto" style={{ maxHeight: '240px', borderColor: 'var(--cafe-border)' }}>
          {repairItems.length === 0 ? (
            <p className="text-center py-6 text-sm italic" style={{ color: 'var(--cafe-text-muted)' }}>No repairs found</p>
          ) : (
            <table className="w-full text-sm">
              <thead style={{ backgroundColor: 'var(--cafe-bg)' }}>
                <tr>
                  <th className="text-left px-4 py-2 font-semibold">Service</th>
                  <th className="text-left px-4 py-2 font-semibold">Category</th>
                  <th className="text-right px-4 py-2 font-semibold">Price</th>
                </tr>
              </thead>
              <tbody>
                {repairItems.map(item => (
                  <tr key={item.key} style={{ borderTop: '1px solid var(--cafe-border)' }}>
                    <td className="px-4 py-2" style={{ color: 'var(--cafe-text)' }}>{item.name}</td>
                    <td className="px-4 py-2" style={{ color: 'var(--cafe-text-muted)' }}>{item.group_label}</td>
                    <td className="px-4 py-2 text-right font-medium" style={{ color: 'var(--cafe-amber)' }}>${(item.price_cents / 100).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Cpu size={20} style={{ color: 'var(--cafe-amber)' }} />
          <h2 className="text-base font-semibold" style={{ color: 'var(--cafe-text)' }}>Movement Database</h2>
        </div>
        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--cafe-text-muted)' }} />
          <input
            type="text"
            placeholder="Search movements by name or caliber…"
            value={movementSearch}
            onChange={e => setMovementSearch(e.target.value)}
            className="w-full h-9 rounded-lg border pl-8 pr-3 text-sm outline-none focus:ring-2"
            style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
          />
        </div>
        <div className="rounded-lg border overflow-y-auto" style={{ maxHeight: '320px', borderColor: 'var(--cafe-border)' }}>
          {filteredMovements.length === 0 ? (
            <p className="text-center py-6 text-sm italic" style={{ color: 'var(--cafe-text-muted)' }}>No movements found</p>
          ) : (
            <table className="w-full text-sm">
              <thead style={{ backgroundColor: 'var(--cafe-bg)' }}>
                <tr>
                  <th className="text-left px-4 py-2 font-semibold">Movement</th>
                  <th className="text-right px-4 py-2 font-semibold">Quote</th>
                </tr>
              </thead>
              <tbody>
                {filteredMovements.slice(0, 100).map(m => (
                  <tr key={m.key} style={{ borderTop: '1px solid var(--cafe-border)' }}>
                    <td className="px-4 py-2" style={{ color: 'var(--cafe-text)' }}>{m.name}</td>
                    <td className="px-4 py-2 text-right font-medium" style={{ color: 'var(--cafe-amber)' }}>
                      {m.quote_cents != null ? `$${(m.quote_cents / 100).toFixed(2)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {filteredMovements.length > 100 && (
            <p className="text-center py-2 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
              Showing 100 of {filteredMovements.length} movements. Refine search to see more.
            </p>
          )}
        </div>
      </Card>
    </div>
  )
}

export default function DatabasePage() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<CsvImportResult | null>(null)
  const [error, setError] = useState('')
  const [clearTabs, setClearTabs] = useState<string[]>(['watch', 'shoe', 'auto_key'])

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setResult(null)
    setError('')
  }

  async function handleImport() {
    if (!file) return
    setUploading(true)
    setError('')
    setResult(null)
    try {
      const { data } = await importCsv(file, { replaceExisting, clearTabs })
      setResult(data)
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
    } catch (err: unknown) {
      const apiErr = err as { response?: { status?: number; data?: { detail?: string } | string }; message?: string }
      const detail =
        typeof apiErr.response?.data === 'string'
          ? apiErr.response.data
          : apiErr.response?.data?.detail
      const status = apiErr.response?.status
      setError(detail || (status ? `Import failed (HTTP ${status}).` : apiErr.message || 'Import failed. Check the CSV format and try again.'))
    }
    setUploading(false)
  }

  const [activeTab, setActiveTab] = useState<'import' | 'catalogue'>('import')

  return (
    <div>
      <PageHeader title="Database" />

      <div className="mb-6 inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
        <button
          type="button"
          className="px-4 py-2 text-sm font-semibold rounded-md transition"
          style={{
            backgroundColor: activeTab === 'import' ? 'var(--cafe-paper)' : 'transparent',
            color: activeTab === 'import' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
          }}
          onClick={() => setActiveTab('import')}
        >
          Import Data
        </button>
        <button
          type="button"
          className="px-4 py-2 text-sm font-semibold rounded-md transition"
          style={{
            backgroundColor: activeTab === 'catalogue' ? 'var(--cafe-paper)' : 'transparent',
            color: activeTab === 'catalogue' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
          }}
          onClick={() => setActiveTab('catalogue')}
        >
          Watch Catalogue
        </button>
      </div>

      {activeTab === 'catalogue' ? (
        <div className="max-w-3xl">
          <WatchCatalogueTab />
        </div>
      ) : (
      <div className="max-w-2xl space-y-6">
        {/* File Import Card */}
        <Card className="p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ backgroundColor: '#EEE6DA' }}>
              <FileSpreadsheet size={20} style={{ color: 'var(--cafe-gold-dark)' }} />
            </div>
            <div>
              <h2 className="text-base font-semibold" style={{ color: 'var(--cafe-text)' }}>Import Data File</h2>
              <p className="text-sm mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>
                Upload a CSV or Excel file to bulk-import historical repair records. The file should include columns like{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>customer_name</code>,{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>phone_number</code>,{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>date_in</code>,{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>brand_case_numbers</code>,{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>status</code>,{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>quote_price</code>,{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>repair_notes</code>. Common aliases like{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>customer</code>,{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>phone</code>,{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>created_at</code>,{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>brand</code>,{' '}
                <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-mid)' }}>notes</code> are also accepted.
              </p>
            </div>
          </div>

          {/* Drop zone */}
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,.xls,.xlsm,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            onClick={() => fileRef.current?.click()}
            className="w-full border-2 border-dashed rounded-lg p-8 transition-colors text-center"
            style={{ borderColor: 'var(--cafe-border-2)' }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--cafe-amber)'; e.currentTarget.style.backgroundColor = '#FEF0DC' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--cafe-border-2)'; e.currentTarget.style.backgroundColor = 'transparent' }}
          >
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <FileSpreadsheet size={32} style={{ color: 'var(--cafe-amber)' }} />
                <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{file.name}</p>
                <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{(file.size / 1024).toFixed(1)} KB · Click to change</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2" style={{ color: 'var(--cafe-text-muted)' }}>
                <Upload size={32} />
                <p className="text-sm font-medium">Click to select a CSV or Excel file (.csv, .xlsx, .xls, .xlsm)</p>
                <p className="text-xs">or drag and drop</p>
              </div>
            )}
          </button>

          {/* Replace options */}
          <div className="mt-4 space-y-3">
            <label className="flex items-start gap-2 text-sm cursor-pointer" style={{ color: 'var(--cafe-text-mid)' }}>
              <input
                type="checkbox"
                checked={replaceExisting}
                onChange={(e) => setReplaceExisting(e.target.checked)}
                className="mt-0.5"
              />
              <span>
                Replace existing data before import
                <span className="block text-xs" style={{ color: '#9B5A4A' }}>
                  When enabled, selected tabs below will be cleared before importing.
                </span>
              </span>
            </label>
            {replaceExisting && (
              <div className="pl-6 space-y-2 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
                <p className="font-medium" style={{ color: 'var(--cafe-text)' }}>Clear these tabs:</p>
                {[
                  { key: 'watch', label: 'Watch (customers, watches, jobs, quotes, invoices)' },
                  { key: 'shoe', label: 'Shoe (shoes, shoe repair jobs)' },
                  { key: 'auto_key', label: 'Auto key (auto key jobs, quotes, invoices)' },
                ].map(({ key, label }) => (
                  <label key={key} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={clearTabs.includes(key)}
                      onChange={(e) => {
                        if (e.target.checked) setClearTabs((t) => [...t, key])
                        else setClearTabs((t) => t.filter((x) => x !== key))
                      }}
                    />
                    {label}
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="mt-4 flex justify-end">
            <Button onClick={handleImport} disabled={!file || uploading}>
              <Upload size={15} />
              {uploading ? 'Importing…' : 'Import file'}
            </Button>
          </div>
        </Card>

        {/* Success result */}
        {result && (
          <Card className="p-5 border-green-200 bg-green-50">
            <div className="flex items-start gap-3">
              <CheckCircle size={20} className="text-green-600 mt-0.5 shrink-0" />
              <div>
                <h3 className="text-sm font-semibold text-green-800">Import Complete</h3>
                <div className="mt-2 grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
                  <span className="text-green-700">Import ID:</span>
                  <span className="font-medium text-green-900 break-all">{result.import_id}</span>
                  <span className="text-green-700">Total rows:</span>
                  <span className="font-medium text-green-900">{result.total_rows}</span>
                  <span className="text-green-700">Imported:</span>
                  <span className="font-medium text-green-900">{result.imported}</span>
                  <span className="text-green-700">Skipped:</span>
                  <span className="font-medium text-green-900">{result.skipped}</span>
                  <span className="text-green-700">Customers created:</span>
                  <span className="font-medium text-green-900">{result.customers_created}</span>
                </div>
                {Object.keys(result.skipped_reasons ?? {}).length > 0 && (
                  <div className="mt-3 text-sm">
                    <p className="font-medium text-green-800">Skip reasons:</p>
                    <ul className="mt-1 space-y-1 text-green-900">
                      {Object.entries(result.skipped_reasons).map(([reason, count]) => (
                        <li key={reason}>{reason}: {count}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </Card>
        )}

        {/* Error */}
        {error && (
          <Card className="p-5 border-red-200 bg-red-50">
            <div className="flex items-start gap-3">
              <AlertCircle size={20} className="text-red-600 mt-0.5 shrink-0" />
              <div>
                <h3 className="text-sm font-semibold text-red-800">Import Failed</h3>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          </Card>
        )}
      </div>
      )}
    </div>
  )
}
