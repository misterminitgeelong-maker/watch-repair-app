import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createWorkLog } from '@/lib/api'
import { Modal, Button, Input, Textarea } from '@/components/ui'

export default function LogWorkModal({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [note, setNote] = useState('')
  const [minutes, setMinutes] = useState('')
  const [error, setError] = useState('')
  const mut = useMutation({
    mutationFn: () => createWorkLog({ repair_job_id: jobId, note, minutes_spent: minutes ? parseInt(minutes) : undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['worklogs', jobId] }); onClose() },
    onError: () => setError('Failed to save work log.'),
  })
  return (
    <Modal title="Log Work" onClose={onClose}>
      <div className="space-y-3">
        <Textarea
          label="Work done *"
          value={note}
          onChange={e => setNote(e.target.value)}
          rows={4}
          placeholder="Cleaned movement, replaced mainspring, re-lubricated escapement…"
          autoFocus
        />
        <Input
          label="Time spent (minutes)"
          type="number"
          min="1"
          value={minutes}
          onChange={e => setMinutes(e.target.value)}
          placeholder="45"
        />
        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={!note || mut.isPending}>{mut.isPending ? 'Saving…' : 'Save Log'}</Button>
        </div>
      </div>
    </Modal>
  )
}
