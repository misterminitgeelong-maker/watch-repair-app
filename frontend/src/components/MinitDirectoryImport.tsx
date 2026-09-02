import { useCallback, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Upload } from 'lucide-react'
import {
  getApiErrorMessage,
  importMinitDirectory,
  type DirectoryImportSummary,
} from '@/lib/api'
import { PARENT_ACCOUNT_QUERY_KEY } from '@/hooks/useParentAccount'
import { PARENT_ACCOUNT_SITES_QUERY_KEY } from '@/hooks/useParentAccountSites'
import { Button, Card, Modal } from '@/components/ui'

const ACCEPT = '.html,.htm,text/html'

export function MinitDirectoryImport() {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [preview, setPreview] = useState<DirectoryImportSummary | null>(null)
  const [applied, setApplied] = useState<DirectoryImportSummary | null>(null)
  const [error, setError] = useState('')

  const previewMut = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Select a file first')
      return importMinitDirectory(file, false).then(r => r.data)
    },
    onSuccess: data => {
      setPreview(data)
      setApplied(null)
      setError('')
    },
    onError: err => {
      setPreview(null)
      setError(getApiErrorMessage(err, 'Could not read that directory export.'))
    },
  })

  const applyMut = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Select a file first')
      return importMinitDirectory(file, true).then(r => r.data)
    },
    onSuccess: data => {
      setApplied(data)
      setError('')
      void qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_QUERY_KEY })
      void qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
      void qc.invalidateQueries({ queryKey: ['minit-operations-overview'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Import failed.')),
  })

  const reset = useCallback(() => {
    setFile(null)
    setPreview(null)
    setApplied(null)
    setError('')
    previewMut.reset()
    applyMut.reset()
  }, [previewMut, applyMut])

  function closeModal() {
    setOpen(false)
    reset()
  }

  function pickFile(next: File | null) {
    if (!next) return
    const name = next.name.toLowerCase()
    if (!name.endsWith('.html') && !name.endsWith('.htm')) {
      setError('Only .html directory exports are supported.')
      return
    }
    setFile(next)
    setPreview(null)
    setApplied(null)
    setError('')
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files?.[0]
    if (dropped) pickFile(dropped)
  }

  const busy = previewMut.isPending || applyMut.isPending

  return (
    <>
      <Button variant="secondary" className="text-sm" onClick={() => setOpen(true)}>
        Import directory
      </Button>

      {open && (
        <Modal onClose={closeModal} title="Import shops + owners from directory export" closeDisabled={busy}>
          <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
            Upload the Organisation Graph HTML export. Each shop's real franchisee gets their own login —
            single-site owners get their own shop, multi-site owners get all of theirs in one account — once
            you send them an invite from Manage shops. Nothing is emailed automatically. Shops with no
            franchisee on file keep the shared HQ login for now. Preview first; nothing is written until you
            apply.
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
            disabled={busy}
          >
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <FileText size={32} style={{ color: 'var(--ms-accent)' }} />
                <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{file.name}</p>
                <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                  {(file.size / 1024).toFixed(1)} KB · Click or drop to change
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2" style={{ color: 'var(--ms-text-muted)' }}>
                <Upload size={32} />
                <p className="text-sm font-medium">Click to select or drag and drop</p>
                <p className="text-xs">.html directory export</p>
              </div>
            )}
          </button>

          {error && (
            <p className="text-sm mb-3" style={{ color: 'var(--ms-danger)' }} role="alert">
              {error}
            </p>
          )}

          {preview && !applied && (
            <Card className="mb-4 p-4 text-sm" style={{ color: 'var(--ms-text)' }}>
              {!preview.hq_parent_found ? (
                <p>{preview.note}</p>
              ) : (
                <>
                  <p className="font-semibold mb-2">Preview — nothing written yet</p>
                  <ul className="space-y-1">
                    <li>{preview.shops?.would_create ?? 0} shops would be created</li>
                    <li>{preview.shops?.already_exists ?? 0} shops already exist (left untouched)</li>
                    <li>{preview.shops?.closed_skipped ?? 0} closed shops skipped</li>
                    <li>
                      {preview.franchisees?.single_site ?? 0} single-site + {preview.franchisees?.multi_site ?? 0}{' '}
                      multi-site franchisees ({preview.franchisees?.would_create_parent_accounts ?? 0} new
                      multi-site accounts)
                    </li>
                  </ul>
                  {((preview.fallback_to_hq_login?.company_owned_no_franchisee ?? 0) > 0 ||
                    (preview.fallback_to_hq_login?.franchisee_missing_email ?? 0) > 0) && (
                    <p className="mt-2 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                      {preview.fallback_to_hq_login?.company_owned_no_franchisee ?? 0} company-owned shops and{' '}
                      {preview.fallback_to_hq_login?.franchisee_missing_email ?? 0} franchisees missing an email
                      will keep the shared HQ login for now.
                    </p>
                  )}
                </>
              )}
            </Card>
          )}

          {applied && (
            <Card className="mb-4 p-4 text-sm" style={{ color: 'var(--ms-text)' }}>
              <p className="font-semibold mb-2">Import complete</p>
              <ul className="space-y-1">
                <li>{applied.created_tenant_count ?? 0} shops created</li>
                <li>{applied.created_owner_count ?? 0} owner logins created</li>
                <li>{applied.created_franchisee_parent_account_count ?? 0} multi-site franchisee accounts created</li>
              </ul>
              <p className="mt-2 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                New owners can't log in yet — send each one an invite from Manage shops when you're ready.
              </p>
            </Card>
          )}

          <div className="flex flex-wrap gap-2 justify-end">
            <Button variant="secondary" onClick={closeModal} disabled={busy}>
              {applied ? 'Done' : 'Cancel'}
            </Button>
            {!applied && (
              <>
                <Button
                  variant="secondary"
                  onClick={() => previewMut.mutate()}
                  disabled={!file || busy}
                >
                  {previewMut.isPending ? 'Checking…' : 'Preview'}
                </Button>
                <Button
                  onClick={() => applyMut.mutate()}
                  disabled={!file || !preview?.hq_parent_found || busy}
                >
                  {applyMut.isPending ? 'Importing…' : 'Apply'}
                </Button>
              </>
            )}
          </div>
        </Modal>
      )}
    </>
  )
}
