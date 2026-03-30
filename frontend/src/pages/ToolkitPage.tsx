import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PageHeader, Button, Card, Spinner, Select, Input } from '@/components/ui'
import MobileServicesSubNav from '@/components/MobileServicesSubNav'
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
  const [toolSearch, setToolSearch] = useState('')

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

  const filteredGroups = useMemo(() => {
    if (!catalog?.groups) return []
    const q = toolSearch.trim().toLowerCase()
    if (!q) return catalog.groups
    return catalog.groups
      .map((g) => ({
        ...g,
        tools: g.tools.filter(
          (t) =>
            t.name.toLowerCase().includes(q) ||
            t.key.toLowerCase().includes(q) ||
            (t.notes && t.notes.toLowerCase().includes(q)),
        ),
      }))
      .filter((g) => g.tools.length > 0)
  }, [catalog?.groups, toolSearch])

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
        <MobileServicesSubNav className="mb-4" />
        <PageHeader title="Mobile toolkit" />
        <p className="text-sm" style={{ color: '#C96A5A' }}>{getApiErrorMessage(catErrObj, 'Could not load toolkit.')}</p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <MobileServicesSubNav />

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <PageHeader title="Mobile toolkit" />
          <p className="text-sm mt-1 max-w-2xl" style={{ color: 'var(--cafe-text-muted)' }}>
            Tick the tools you keep on the van. Pick a scenario to see what you are missing before you roll.
          </p>
        </div>
        <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center lg:flex-col lg:items-end">
          {dirty && (
            <span className="text-xs font-medium text-center sm:text-right" style={{ color: 'var(--cafe-amber)' }}>
              Unsaved changes
            </span>
          )}
          <Button type="button" onClick={() => saveMut.mutate()} disabled={!dirty || saveMut.isPending} className="min-h-11">
            {saveMut.isPending ? 'Saving…' : 'Save my tools'}
          </Button>
        </div>
      </div>

      <details className="rounded-xl border text-sm" style={{ borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}>
        <summary className="cursor-pointer px-4 py-3 font-medium" style={{ color: 'var(--cafe-text-mid)' }}>
          Where the catalog comes from
        </summary>
        <p className="px-4 pb-3 pl-6" style={{ color: 'var(--cafe-text-muted)' }}>
          Ship list:{' '}
          <code className="text-xs rounded px-1" style={{ backgroundColor: 'var(--cafe-surface)' }}>
            backend/seed/mobile_services_tools.json
          </code>
          . Optional regen:{' '}
          <code className="text-xs rounded px-1" style={{ backgroundColor: 'var(--cafe-surface)' }}>
            backend/scripts/generate_mobile_services_tools_from_xlsx.py
          </code>
          .
        </p>
      </details>

      <Card className="p-4 sm:p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
          Scenario check
        </h2>
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <div className="min-w-[200px] flex-1">
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--cafe-text)' }}>
              Scenario
            </label>
            <Select
              value={scenarioId}
              onChange={(e) => {
                setScenarioId(e.target.value)
                setRecommend(null)
              }}
              style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            >
              <option value="">Select…</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </Select>
          </div>
          <Button type="button" variant="secondary" className="min-h-11 w-full sm:w-auto" onClick={runRecommend} disabled={!scenarioId}>
            What do I need?
          </Button>
        </div>
        {recErr && <p className="text-sm mt-3" style={{ color: '#C96A5A' }}>{recErr}</p>}
        {recommend && (
          <div className="mt-4 space-y-3 text-sm" style={{ color: 'var(--cafe-text)' }}>
            <p className="font-medium">
              {recommend.label}{' '}
              <span
                className="ml-2 rounded-full px-2 py-0.5 text-xs font-semibold"
                style={{
                  backgroundColor: recommend.ready_for_required ? '#E8F0E4' : '#FDE9E1',
                  color: recommend.ready_for_required ? '#3B6B42' : '#A2502E',
                }}
              >
                {recommend.ready_for_required ? 'Ready (required covered)' : 'Missing required items'}
              </span>
            </p>
            {recommend.tips && <p style={{ color: 'var(--cafe-text-muted)' }}>{recommend.tips}</p>}
            {recommend.missing_required.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: '#A2502E' }}>
                  Still need
                </p>
                <ul className="list-disc pl-5 space-y-1">
                  {recommend.missing_required.map((r) => (
                    <li key={r.key}>
                      {r.name}
                      {r.group_label ? ` · ${r.group_label}` : ''}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {recommend.missing_nice_to_have.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--cafe-text-muted)' }}>
                  Nice to have
                </p>
                <ul className="list-disc pl-5 space-y-1" style={{ color: 'var(--cafe-text-mid)' }}>
                  {recommend.missing_nice_to_have.map((r) => (
                    <li key={r.key}>{r.name}</li>
                  ))}
                </ul>
              </div>
            )}
            {recommend.ready_for_required && recommend.required.filter((r) => r.via_alternative).length > 0 && (
              <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                Some required roles are covered by substitute tools you ticked.
              </p>
            )}
          </div>
        )}
      </Card>

      <div className="max-w-md">
        <Input label="Filter tools" value={toolSearch} onChange={(e) => setToolSearch(e.target.value)} placeholder="Name, note, or key…" />
      </div>

      {filteredGroups.length === 0 && toolSearch.trim() && (
        <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
          No tools match that filter.
        </p>
      )}

      {filteredGroups.map((g, idx) => (
        <details
          key={g.id}
          className="rounded-2xl border overflow-hidden"
          style={{ borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-surface)' }}
          open={idx === 0 && !toolSearch.trim()}
        >
          <summary
            className="cursor-pointer list-none px-4 py-3.5 text-sm font-semibold uppercase tracking-wide flex items-center justify-between gap-2"
            style={{ color: 'var(--cafe-amber)', backgroundColor: 'var(--cafe-bg)' }}
          >
            <span>{g.label}</span>
            <span className="text-xs font-normal normal-case tracking-normal" style={{ color: 'var(--cafe-text-muted)' }}>
              {g.tools.length} tool{g.tools.length !== 1 ? 's' : ''}
            </span>
          </summary>
          <ul className="px-4 pb-4 pt-2 space-y-2 border-t" style={{ borderColor: 'var(--cafe-border)' }}>
            {g.tools.map((t) => (
              <li key={t.key}>
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
        </details>
      ))}
    </div>
  )
}
