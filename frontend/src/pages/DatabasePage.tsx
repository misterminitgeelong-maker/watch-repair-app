import { useState, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Upload, CheckCircle, AlertCircle, FileSpreadsheet } from 'lucide-react'
import axios from 'axios'
import { importCsv, getApiErrorMessage, type CsvImportResult, type CsvImportTarget } from '@/lib/api'
import { PageHeader, Card, Button, Input } from '@/components/ui'
import WatchCatalogueTab from '@/components/WatchCatalogueTab'

export default function DatabasePage() {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [dryRun, setDryRun] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<CsvImportResult | null>(null)
  const [error, setError] = useState('')
  const [importTarget, setImportTarget] = useState<CsvImportTarget>('watch')
  const [excelSheetName, setExcelSheetName] = useState('')

  const clearTabForTarget = (t: CsvImportTarget): string[] =>
    t === 'watch' ? ['watch'] : t === 'shoe' ? ['shoe'] : ['auto_key']

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setResult(null)
    setError('')
  }

  async function runImport(opts: { dryRun: boolean }) {
    if (!file) return
    setUploading(true)
    setError('')
    setResult(null)
    try {
      const { data } = await importCsv(file, {
        replaceExisting,
        clearTabs: clearTabForTarget(importTarget),
        dryRun: opts.dryRun,
        sheetName: excelSheetName.trim() || undefined,
        importTarget,
      })
      setResult(data)
      if (!opts.dryRun) {
        setFile(null)
        if (fileRef.current) fileRef.current.value = ''
        void qc.invalidateQueries({ queryKey: ['jobs'] })
        void qc.invalidateQueries({ queryKey: ['quotes'] })
        void qc.invalidateQueries({ queryKey: ['customers'] })
        void qc.invalidateQueries({ queryKey: ['customer-accounts'] })
        void qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
        void qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
        void qc.invalidateQueries({
          predicate: (q) => {
            const k = q.queryKey[0]
            return typeof k === 'string' && k.startsWith('reports')
          },
        })
      }
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 429) {
        setError('Too many import attempts — try again in a minute.')
      } else {
        setError(
          getApiErrorMessage(
            err,
            'Import failed. Try saving Excel as CSV (UTF-8) or check column names (customer_name, phone_number, date_in, brand_case_numbers, quote_price, repair_notes).',
          ),
        )
      }
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
            backgroundColor: activeTab === 'import' ? 'var(--ms-surface)' : 'transparent',
            color: activeTab === 'import' ? 'var(--ms-text)' : 'var(--ms-text-muted)',
          }}
          onClick={() => setActiveTab('import')}
        >
          Import Data
        </button>
        <button
          type="button"
          className="px-4 py-2 text-sm font-semibold rounded-md transition"
          style={{
            backgroundColor: activeTab === 'catalogue' ? 'var(--ms-surface)' : 'transparent',
            color: activeTab === 'catalogue' ? 'var(--ms-text)' : 'var(--ms-text-muted)',
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
              <FileSpreadsheet size={20} style={{ color: 'var(--ms-accent-hover)' }} />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-base font-semibold" style={{ color: 'var(--ms-text)' }}>Import Data File</h2>
              <p className="text-sm mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                Choose which module receives the file. Rows only create records in that module (watch jobs, shoe jobs, or mobile services jobs).
              </p>
              <div className="mt-3 inline-flex flex-wrap gap-1 rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
                {(
                  [
                    { id: 'watch' as const, label: 'Watch repairs' },
                    { id: 'shoe' as const, label: 'Shoe repairs' },
                    { id: 'mobile' as const, label: 'Mobile services' },
                  ] as const
                ).map(({ id, label }) => (
                  <button
                    key={id}
                    type="button"
                    className="px-3 py-1.5 text-sm font-semibold rounded-md transition"
                    style={{
                      backgroundColor: importTarget === id ? 'var(--ms-surface)' : 'transparent',
                      color: importTarget === id ? 'var(--ms-text)' : 'var(--ms-text-muted)',
                    }}
                    onClick={() => {
                      setImportTarget(id)
                      setResult(null)
                      setError('')
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {importTarget === 'watch' && (
                <p className="text-sm mt-3" style={{ color: 'var(--ms-text-muted)' }}>
                  Expected columns include{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>customer</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>phone</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>date_in</code> /{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>date_time</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>brand</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>status</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>quote</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>notes</code> /{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>job_description</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>ticket_number</code>.
                  Excel: we auto-pick the sheet that looks most like a job log; override below if needed.
                </p>
              )}
              {importTarget === 'shoe' && (
                <p className="text-sm mt-3" style={{ color: 'var(--ms-text-muted)' }}>
                  Creates customers, shoes, and shoe repair jobs. Useful headers:{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>customer</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>phone</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>brand</code> /{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>shoe_type</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>color</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>job_description</code> /{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>notes</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>quote</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>status</code>.
                </p>
              )}
              {importTarget === 'mobile' && (
                <p className="text-sm mt-3" style={{ color: 'var(--ms-text-muted)' }}>
                  Creates customers and mobile services (auto key) jobs. Useful headers:{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>customer</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>phone</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>address</code> /{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>job_address</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>job_description</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>vehicle_make</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>vehicle_model</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>quote</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>status</code>,{' '}
                  <code className="text-xs px-1 py-0.5 rounded" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>source</code> (salesperson).
                </p>
              )}
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
            style={{ borderColor: 'var(--ms-border-strong)' }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--ms-accent)'; e.currentTarget.style.backgroundColor = '#FEF0DC' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--ms-border-strong)'; e.currentTarget.style.backgroundColor = 'transparent' }}
          >
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <FileSpreadsheet size={32} style={{ color: 'var(--ms-accent)' }} />
                <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{file.name}</p>
                <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{(file.size / 1024).toFixed(1)} KB · Click to change</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2" style={{ color: 'var(--ms-text-muted)' }}>
                <Upload size={32} />
                <p className="text-sm font-medium">Click to select a CSV or Excel file (.csv, .xlsx, .xls, .xlsm)</p>
                <p className="text-xs">or drag and drop</p>
              </div>
            )}
          </button>

          <div className="mt-4">
            <Input
              label="Excel sheet name (optional)"
              value={excelSheetName}
              onChange={e => setExcelSheetName(e.target.value)}
              placeholder="e.g. Repairs — leave blank to auto-detect"
            />
          </div>

          {/* Replace options */}
          <div className="mt-4 space-y-3">
            <label className="flex items-start gap-2 text-sm cursor-pointer" style={{ color: 'var(--ms-text-mid)' }}>
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="mt-0.5"
              />
              <span>
                Dry run (preview only — recommended)
                <span className="block text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                  Validates the file and shows a summary without writing data. Turn off to apply a real import.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2 text-sm cursor-pointer" style={{ color: 'var(--ms-text-mid)' }}>
              <input
                type="checkbox"
                checked={replaceExisting}
                onChange={(e) => setReplaceExisting(e.target.checked)}
                className="mt-0.5"
              />
              <span>
                Replace existing data in this module before import
                <span className="block text-xs" style={{ color: '#9B5A4A' }}>
                  When enabled, all existing{' '}
                  {importTarget === 'watch' ? 'watch repair jobs (and related quotes, watches for this shop)' : importTarget === 'shoe' ? 'shoe repair jobs and shoe records' : 'mobile services jobs, quotes, and invoices'}{' '}
                  for your shop are removed, then the file is imported. Other modules are not cleared.
                </span>
              </span>
            </label>
          </div>

          <div className="mt-4 flex flex-wrap justify-end gap-2">
            <Button onClick={() => void runImport({ dryRun })} disabled={!file || uploading}>
              <Upload size={15} />
              {uploading ? 'Working…' : dryRun ? 'Preview import' : 'Run import'}
            </Button>
          </div>
        </Card>

        {result && (
          <Card className="p-5 border-green-200 bg-green-50">
            <div className="flex items-start gap-3">
              <CheckCircle size={20} className="text-green-600 mt-0.5 shrink-0" />
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold text-green-800">
                  {result.dry_run ? 'Dry run complete' : 'Import complete'}
                </h3>
                <div className="mt-2 grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
                  <span className="text-green-700">Dry run:</span>
                  <span className="font-medium text-green-900">{result.dry_run ? 'Yes' : 'No'}</span>
                  <span className="text-green-700">Import ID:</span>
                  <span className="font-medium text-green-900 break-all">{result.import_id}</span>
                  <span className="text-green-700">Total rows:</span>
                  <span className="font-medium text-green-900">{result.total_rows}</span>
                  {result.import_target && (
                    <>
                      <span className="text-green-700">Import target:</span>
                      <span className="font-medium text-green-900">{result.import_target}</span>
                    </>
                  )}
                  {result.source_sheet && (
                    <>
                      <span className="text-green-700">Excel sheet:</span>
                      <span className="font-medium text-green-900">{result.source_sheet}</span>
                    </>
                  )}
                  <span className="text-green-700">Imported:</span>
                  <span className="font-medium text-green-900">{result.imported}</span>
                  <span className="text-green-700">Skipped:</span>
                  <span className="font-medium text-green-900">{result.skipped}</span>
                  <span className="text-green-700">Customers created:</span>
                  <span className="font-medium text-green-900">{result.customers_created}</span>
                  {result.duplicate_customer_rows_in_file != null && (
                    <>
                      <span className="text-green-700">Duplicate customer rows in file:</span>
                      <span className="font-medium text-green-900">{result.duplicate_customer_rows_in_file}</span>
                    </>
                  )}
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
                {result.dry_run && file && (
                  <div className="mt-4 rounded-lg px-3 py-3" style={{ backgroundColor: '#FEF9E8', border: '1px solid #E8D4A0' }}>
                    <p className="text-sm font-medium text-green-900">Ready to apply?</p>
                    <p className="text-xs mt-1 text-green-800">
                      Your file is still selected. Turn off &quot;Dry run&quot; above (or use the button below) to write data for real.
                    </p>
                    <Button
                      className="mt-3"
                      disabled={uploading}
                      onClick={() => {
                        void runImport({ dryRun: false })
                        setDryRun(false)
                      }}
                    >
                      Run import (apply changes)
                    </Button>
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
