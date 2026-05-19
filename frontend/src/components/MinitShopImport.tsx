import { useCallback, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FileSpreadsheet, Upload } from 'lucide-react'
import {
  getApiErrorMessage,
  importParentShopsFromXlsx,
  type ParentImportShopsResult,
} from '@/lib/api'
import { Button, Card, Modal } from '@/components/ui'

const ACCEPT = '.xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

export function MinitShopImport() {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [result, setResult] = useState<ParentImportShopsResult | null>(null)
  const [error, setError] = useState('')

  const importMut = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Select a file first')
      return importParentShopsFromXlsx(file).then(r => r.data)
    },
    onSuccess: data => {
      setResult(data)
      setError('')
      void qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      void qc.invalidateQueries({ queryKey: ['minit-operations-overview'] })
    },
    onError: err => {
      setResult(null)
      setError(getApiErrorMessage(err, 'Import failed.'))
    },
  })

  const reset = useCallback(() => {
    setFile(null)
    setResult(null)
    setError('')
    importMut.reset()
  }, [importMut])

  function closeModal() {
    setOpen(false)
    reset()
  }

  function pickFile(next: File | null) {
    if (!next) return
    const name = next.name.toLowerCase()
    if (!name.endsWith('.xlsx') && !name.endsWith('.xlsm')) {
      setError('Only .xlsx or .xlsm workbooks are supported.')
      return
    }
    setFile(next)
    setError('')
    setResult(null)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files?.[0]
    if (dropped) pickFile(dropped)
  }

  return (
    <>
      <Button variant="secondary" className="text-sm" onClick={() => setOpen(true)}>
        Import shops
      </Button>

      {open && (
      <Modal onClose={closeModal} title="Import shops from Excel" closeDisabled={importMut.isPending}>
        <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
          Upload a workbook with columns Shop #, Shop Name, Area, and Region (sheet &quot;Shops&quot; or
          &quot;TSS Scores&quot;). Existing shop numbers are updated; new ones are created as booking-only shops.
        </p>

        <input
          ref={fileRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={e => pickFile(e.target.files?.[0] ?? null)}
        />

        <button
          type="button"
          className="w-full border-2 border-dashed rounded-lg p-8 transition-colors text-center mb-4"
          style={{
            borderColor: dragOver ? 'var(--ms-accent)' : 'var(--ms-border-strong)',
            backgroundColor: dragOver ? '#FEF0DC' : 'transparent',
          }}
          onClick={() => fileRef.current?.click()}
          onDragOver={e => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          disabled={importMut.isPending}
        >
          {file ? (
            <div className="flex flex-col items-center gap-2">
              <FileSpreadsheet size={32} style={{ color: 'var(--ms-accent)' }} />
              <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{file.name}</p>
              <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                {(file.size / 1024).toFixed(1)} KB · Click or drop to change
              </p>
            </div>
          ) : (
            <DropZoneHint />
          )}
        </button>

        {error && (
          <p className="text-sm mb-3" style={{ color: 'var(--ms-danger)' }} role="alert">
            {error}
          </p>
        )}

        {result && (
          <Card className="mb-4 p-4 text-sm" style={{ color: 'var(--ms-text)' }}>
            <p className="font-semibold mb-2">Import complete</p>
            {result.sheet_name && (
              <p className="text-xs mb-2" style={{ color: 'var(--ms-text-muted)' }}>
                Sheet: {result.sheet_name} · {result.parsed_count} rows parsed
              </p>
            )}
            <ul className="space-y-1 text-sm">
              <li>{result.created_count} created</li>
              <li>{result.updated_count} updated</li>
              <li>{result.skipped_count} skipped (unchanged or duplicate)</li>
            </ul>
            {result.errors.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-semibold mb-1" style={{ color: 'var(--ms-danger)' }}>
                  Row warnings ({result.errors.length})
                </p>
                <ul
                  className="text-xs max-h-32 overflow-y-auto space-y-0.5"
                  style={{ color: 'var(--ms-text-muted)' }}
                >
                  {result.errors.slice(0, 50).map(msg => (
                    <li key={msg}>{msg}</li>
                  ))}
                  {result.errors.length > 50 && <li>…and {result.errors.length - 50} more</li>}
                </ul>
              </div>
            )}
          </Card>
        )}

        <div className="flex flex-wrap gap-2 justify-end">
          <Button variant="secondary" onClick={closeModal} disabled={importMut.isPending}>
            {importMut.isPending ? 'Close' : 'Done'}
          </Button>
          <Button onClick={() => importMut.mutate()} disabled={!file || importMut.isPending}>
            {importMut.isPending ? 'Importing…' : 'Import'}
          </Button>
        </div>
      </Modal>
      )}
    </>
  )
}

function DropZoneHint() {
  return (
    <div className="flex flex-col items-center gap-2" style={{ color: 'var(--ms-text-muted)' }}>
      <Upload size={32} />
      <p className="text-sm font-medium">Click to select or drag and drop</p>
      <p className="text-xs">.xlsx or .xlsm (max 5 MB)</p>
    </div>
  )
}
