import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PageHeader, Button, Card, Spinner, Select } from '@/components/ui'
import {
  getApiErrorMessage,
  getToolkitCatalog,
  getToolkitMySelection,
  postToolkitRecommend,
  putToolkitMySelection,
  type ToolkitRecommendResponse,
} from '@/lib/api'

export default function ToolkitPage() {
  const qc = useQueryClient()
  const [localKeys, setLocalKeys] = useState<Set<string>>(new Set())
  const [scenarioId, setScenarioId] = useState('')
  const [recommend, setRecommend] = useState<ToolkitRecommendResponse | null>(null)
  const [recErr, setRecErr] = useState('')

  const { data: catalog, isLoading: catLoading, isError: catErr, error: catErrObj } = useQuery({
    queryKey: ['toolkit', 'catalog'],
    queryFn: () => getToolkitCatalog().then((r) => r.data),
  })
  const { data: saved, isLoading: selLoading } = useQuery({
    queryKey: ['toolkit', 'my-selection'],
    queryFn: () => getToolkitMySelection().then((r) => r.data),
  })

  useEffect(() => {
    if (saved?.tool_keys) setLocalKeys(new Set(saved.tool_keys))
  }, [saved?.tool_keys])

  const saveMut = useMutation({
    mutationFn: () => putToolkitMySelection([...localKeys]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['toolkit', 'my-selection'] })
      setRecommend(null)
    },
  })

  const scenarios = catalog?.scenarios ?? []

  const dirty = useMemo(() => {
    const a = [...localKeys].sort().join(',')
    const b = [...(saved?.tool_keys ?? [])].sort().join(',')
    return a !== b
  }, [localKeys, saved?.tool_keys])

  const toggle = (key: string) => {
    setLocalKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const runRecommend = () => {
    setRecErr('')
    setRecommend(null)
    if (!scenarioId) {
      setRecErr('Choose a scenario first.')
      return
    }
    postToolkitRecommend(scenarioId)
      .then((r) => setRecommend(r.data))
      .catch((e) => setRecErr(getApiErrorMessage(e, 'Could not load recommendation')))
  }

  if (catLoading || selLoading) return <Spinner />
  if (catErr) {
    return (
      <div>
        <PageHeader title="Mobile toolkit" />
        <p className="text-sm" style={{ color: '#C96A5A' }}>{getApiErrorMessage(catErrObj, 'Could not load toolkit.')}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mobile toolkit"
        action={
          <Button type="button" onClick={() => saveMut.mutate()} disabled={!dirty || saveMut.isPending}>
            {saveMut.isPending ? 'Saving…' : 'Save my tools'}
          </Button>
        }
      />
      <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
        Tick the tools you carry for Mobile Services. Pick a scenario to see gaps and acceptable substitutes. The canonical list is{' '}
        <code className="text-xs rounded px-1" style={{ backgroundColor: 'var(--cafe-surface)' }}>backend/seed/mobile_services_tools.json</code>
        . Regenerate from your Locksmith Master workbook with{' '}
        <code className="text-xs rounded px-1" style={{ backgroundColor: 'var(--cafe-surface)' }}>backend/scripts/generate_mobile_services_tools_from_xlsx.py</code>
        , or edit the JSON directly.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
          <Link
            to="/auto-key"
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
            style={{ backgroundColor: 'transparent', color: 'var(--cafe-text-muted)', textDecoration: 'none' }}
          >
            Mobile Services
          </Link>
          <span
            className="px-3 py-1.5 text-xs font-semibold rounded-md"
            style={{ backgroundColor: 'var(--cafe-paper)', color: 'var(--cafe-text)' }}
          >
            Toolkit
          </span>
        </div>
      </div>

      <Card className="p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
          Scenario recommendation
        </h2>
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1">
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--cafe-text)' }}>Scenario</label>
            <Select
              value={scenarioId}
              onChange={(e) => { setScenarioId(e.target.value); setRecommend(null) }}
              style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            >
              <option value="">Select…</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </Select>
          </div>
          <Button type="button" variant="secondary" onClick={runRecommend} disabled={!scenarioId}>
            What do I need?
          </Button>
        </div>
        {recErr && <p className="text-sm mt-3" style={{ color: '#C96A5A' }}>{recErr}</p>}
        {recommend && (
          <div className="mt-4 space-y-3 text-sm" style={{ color: 'var(--cafe-text)' }}>
            <p className="font-medium">
              {recommend.label}
              {' '}
              <span
                className="ml-2 rounded-full px-2 py-0.5 text-xs font-semibold"
                style={{
                  backgroundColor: recommend.ready_for_required ? '#E8F0E4' : '#FDE9E1',
                  color: recommend.ready_for_required ? '#3B6B42' : '#A2502E',
                }}
              >
                {recommend.ready_for_required ? 'Ready (required tools covered)' : 'Missing required items'}
              </span>
            </p>
            {recommend.tips && (
              <p style={{ color: 'var(--cafe-text-muted)' }}>{recommend.tips}</p>
            )}
            {recommend.missing_required.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: '#A2502E' }}>Still need</p>
                <ul className="list-disc pl-5 space-y-1">
                  {recommend.missing_required.map((r) => (
                    <li key={r.key}>{r.name}{r.group_label ? ` · ${r.group_label}` : ''}</li>
                  ))}
                </ul>
              </div>
            )}
            {recommend.missing_nice_to_have.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Nice to have</p>
                <ul className="list-disc pl-5 space-y-1" style={{ color: 'var(--cafe-text-mid)' }}>
                  {recommend.missing_nice_to_have.map((r) => (
                    <li key={r.key}>{r.name}</li>
                  ))}
                </ul>
              </div>
            )}
            {recommend.ready_for_required && recommend.required.filter((r) => r.via_alternative).length > 0 && (
              <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                Some required roles are covered by substitute tools you ticked (see catalogue alternatives in JSON).
              </p>
            )}
          </div>
        )}
      </Card>

      {catalog?.groups.map((g) => (
        <Card key={g.id} className="p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--cafe-amber)' }}>
            {g.label}
          </h3>
          <ul className="space-y-2">
            {g.tools.map((t) => (
              <li key={t.key} className="flex gap-3 items-start">
                <label className="flex gap-3 cursor-pointer touch-manipulation min-h-11 items-start">
                  <input
                    type="checkbox"
                    className="mt-1 size-4 shrink-0 rounded border"
                    style={{ accentColor: 'var(--cafe-amber)' }}
                    checked={localKeys.has(t.key)}
                    onChange={() => toggle(t.key)}
                  />
                  <span>
                    <span className="font-medium" style={{ color: 'var(--cafe-text)' }}>{t.name}</span>
                    {t.notes && (
                      <span className="block text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>{t.notes}</span>
                    )}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  )
}
