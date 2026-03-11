import { useState, useRef } from 'react'
import { Upload, CheckCircle, AlertCircle, FileSpreadsheet } from 'lucide-react'
import { importCsv, type CsvImportResult } from '@/lib/api'
import { PageHeader, Card, Button } from '@/components/ui'

export default function DatabasePage() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<CsvImportResult | null>(null)
  const [error, setError] = useState('')

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
      const { data } = await importCsv(file)
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

  return (
    <div>
      <PageHeader title="Database" />

      <div className="max-w-2xl space-y-6">
        {/* File Import Card */}
        <Card className="p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ backgroundColor: '#F5E8CC' }}>
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

          {/* Import button */}
          <div className="flex justify-end mt-4">
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
    </div>
  )
}
