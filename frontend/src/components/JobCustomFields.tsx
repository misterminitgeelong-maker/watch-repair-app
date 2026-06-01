import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { patchJobCustomFields, getApiErrorMessage } from '@/lib/api'
import { useToast } from '@/lib/toast'
import { Button, Card, Input } from '@/components/ui'

type Props = {
  jobType: 'repair_job' | 'auto_key_job' | 'shoe_repair_job'
  jobId: string
  initialJson?: string | null
}

function parseFields(json?: string | null): Record<string, string> {
  if (!json) return {}
  try {
    const o = JSON.parse(json) as Record<string, unknown>
    return Object.fromEntries(
      Object.entries(o).map(([k, v]) => [k, String(v ?? '')]),
    )
  } catch {
    return {}
  }
}

export default function JobCustomFields({ jobType, jobId, initialJson }: Props) {
  const toast = useToast()
  const [fields, setFields] = useState<Record<string, string>>(() => parseFields(initialJson))
  const [newKey, setNewKey] = useState('')
  const [newVal, setNewVal] = useState('')

  useEffect(() => {
    setFields(parseFields(initialJson))
  }, [initialJson, jobId])

  const saveMut = useMutation({
    mutationFn: () => patchJobCustomFields(jobType, jobId, fields),
    onSuccess: () => toast.success('Custom fields saved'),
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, 'Failed to save')),
  })

  const entries = Object.entries(fields)

  return (
    <Card title="Custom fields">
      <div className="space-y-2">
        {entries.length === 0 && (
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>No custom fields yet.</p>
        )}
        {entries.map(([k, v]) => (
          <div key={k} className="flex gap-2 items-center">
            <span className="text-xs font-medium w-28 shrink-0 truncate" style={{ color: 'var(--ms-text-muted)' }}>{k}</span>
            <Input
              value={v}
              onChange={e => setFields(f => ({ ...f, [k]: e.target.value }))}
              className="flex-1"
            />
            <Button
              variant="ghost"
              className="text-xs shrink-0"
              onClick={() => setFields(f => {
                const next = { ...f }
                delete next[k]
                return next
              })}
            >
              Remove
            </Button>
          </div>
        ))}
        <div className="flex gap-2 flex-wrap items-end pt-1">
          <Input label="Field name" value={newKey} onChange={e => setNewKey(e.target.value)} className="flex-1 min-w-[120px]" />
          <Input label="Value" value={newVal} onChange={e => setNewVal(e.target.value)} className="flex-1 min-w-[120px]" />
          <Button
            variant="secondary"
            disabled={!newKey.trim()}
            onClick={() => {
              setFields(f => ({ ...f, [newKey.trim()]: newVal }))
              setNewKey('')
              setNewVal('')
            }}
          >
            Add
          </Button>
        </div>
        <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
          {saveMut.isPending ? 'Saving…' : 'Save fields'}
        </Button>
      </div>
    </Card>
  )
}
