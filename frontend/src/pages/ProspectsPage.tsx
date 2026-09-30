import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getApiErrorMessage, getProspectContactDetails, listProspectCategories, listProspectRegions, searchProspects, listProspectLeads, saveProspectLead, type Prospect } from '@/lib/api'
import { Button, Card, Input, PageHeader, Select, Spinner } from '@/components/ui'
import MobileServicesSubNav from '@/components/MobileServicesSubNav'
import { useAuth } from '@/context/AuthContext'

type Search = { category: string; state: string; suburbs: string[]; live: boolean }

function ProspectResult({ prospect, saved, state }: { prospect: Prospect; saved: boolean; state: string }) {
  const qc = useQueryClient()
  const [contact, setContact] = useState<{ phone: string | null; website: string | null; attributions: string[] } | null>(null)
  const p = { ...prospect, phone: contact?.phone || prospect.phone, website: contact?.website || prospect.website }
  const lookup = useMutation({ mutationFn: () => getProspectContactDetails(p.place_id), onSuccess: r => {
    setContact(r.data)
    void qc.invalidateQueries({ queryKey: ['prospect-leads'] })
    void qc.invalidateQueries({ queryKey: ['inbound-leads'] })
  } })
  const save = useMutation({ mutationFn: () => saveProspectLead({ ...p, phone: p.phone ?? undefined, website: p.website ?? undefined, rating: p.rating ?? undefined, review_count: p.review_count ?? undefined, state_code: state }), onSuccess: () => {
    void qc.invalidateQueries({ queryKey: ['prospect-leads'] })
    void qc.invalidateQueries({ queryKey: ['inbound-leads'] })
  } })
  return <li className="rounded-lg border p-4 space-y-3" style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border)' }}>
    <div className="flex flex-wrap items-start justify-between gap-2"><h2 className="font-semibold">{p.name}</h2>{saved && <Link className="text-sm min-h-11" to="/auto-key/prospects/board">On board →</Link>}</div>
    <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>{p.address}</p>
    <div className="flex flex-wrap gap-3 text-sm">
      {p.phone && <a className="min-h-11" href={`tel:${p.phone}`}>Call {p.phone}</a>}
      {p.website && <a className="min-h-11" href={p.website} target="_blank" rel="noopener noreferrer">Website ↗</a>}
      {p.rating != null && <span>★ {p.rating} ({p.review_count ?? 0})</span>}
    </div>
    {!p.phone && !p.website && <p className="text-sm">No phone or website recorded.</p>}
    <div className="flex flex-wrap gap-2">
      {!saved && <Button disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save to board'}</Button>}
      {(!p.phone || !p.website) && <Button variant="secondary" disabled={lookup.isPending} onClick={() => lookup.mutate()}>{lookup.isPending ? 'Looking up…' : 'Find contact details'}</Button>}
      <a className="inline-flex min-h-11 items-center text-sm" href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(p.name + ' ' + p.address)}`} target="_blank" rel="noopener noreferrer">Maps ↗</a>
    </div>
    {contact && !contact.phone && !contact.website && <p role="status" className="text-sm">Google has no phone or website for this business.</p>}
    {contact?.attributions.map(a => <p key={a} className="text-xs">{a}</p>)}
    {(save.error || lookup.error) && <p role="alert" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(save.error || lookup.error)}</p>}
  </li>
}

export default function ProspectsPage() {
  const [url, setUrl] = useSearchParams()
  const { tenantId } = useAuth()
  const filterKey = `prospect-search:${tenantId ?? 'current'}`
  let restored = new URLSearchParams()
  try { restored = new URLSearchParams(sessionStorage.getItem(filterKey) ?? '') } catch { /* Storage may be disabled. */ }
  const parameters = url.has('category') ? url : restored
  const initial: Search = { category: parameters.get('category') ?? '', state: parameters.get('state') ?? '', suburbs: (parameters.get('suburbs') ?? '').split(',').filter(Boolean), live: parameters.get('live') === '1' }
  const [category, setCategory] = useState(initial.category)
  const [state, setState] = useState(initial.state)
  const [suburbs, setSuburbs] = useState(new Set(initial.suburbs))
  const [live, setLive] = useState(initial.live)
  const [submitted, setSubmitted] = useState<Search | null>(initial.category && initial.state && (!initial.live || url.has('category')) ? initial : null)
  const [locality, setLocality] = useState('')
  const [resultFilter, setResultFilter] = useState('')
  const { data: categories, error: categoriesError } = useQuery({ queryKey: ['prospect-categories'], queryFn: () => listProspectCategories().then(r => r.data) })
  const { data: regions, error: regionsError } = useQuery({ queryKey: ['prospect-regions'], queryFn: () => listProspectRegions().then(r => r.data) })
  const { data: leads = [], error: leadsError } = useQuery({ queryKey: ['prospect-leads'], queryFn: () => listProspectLeads().then(r => r.data) })
  const savedIds = useMemo(() => new Set(leads.map(l => l.place_id)), [leads])
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['prospects', submitted],
    queryFn: () => searchProspects(submitted!.category, submitted!.state, submitted!.suburbs, submitted!.live).then(r => r.data),
    enabled: !!submitted, retry: false,
  })
  const available = regions?.suburbs?.[state] ?? []
  const matching = available.filter(s => s.toLowerCase().includes(locality.trim().toLowerCase()))
  const toggle = (suburb: string) => setSuburbs(prev => { const next = new Set(prev); if (next.has(suburb)) next.delete(suburb); else next.add(suburb); return next })
  const search = () => {
    const next = { category, state, suburbs: [...suburbs].sort(), live }
    const parameters = { category, state, suburbs: next.suburbs.join(','), live: live ? '1' : '0' }
    try { sessionStorage.setItem(filterKey, new URLSearchParams(parameters).toString()) } catch { /* Search still works without storage. */ }
    setUrl(parameters)
    if (JSON.stringify(next) === JSON.stringify(submitted)) void refetch()
    else setSubmitted(next)
  }
  const results = (data?.results ?? []).filter(p => `${p.name} ${p.address}`.toLowerCase().includes(resultFilter.toLowerCase()))
  const metadataError = categoriesError || regionsError

  return <div className="p-2 sm:p-6 space-y-4">
    <MobileServicesSubNav />
    <div className="flex flex-wrap items-center justify-between gap-3"><PageHeader title="Prospect Search" /><Link className="min-h-11 inline-flex items-center text-sm" to="/auto-key/prospects/board">View board →</Link></div>
    <Card className="p-4 space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Select id="prospect-category" aria-label="Category" label="Category" value={category} onChange={e => setCategory(e.target.value)}><option value="">Select category</option>{categories?.categories.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}</Select>
        <Select id="prospect-state" aria-label="State" label="State" value={state} onChange={e => { setState(e.target.value); setSuburbs(new Set()); setLocality('') }}><option value="">Select state</option>{regions?.states.map(s => <option key={s.code} value={s.code}>{s.name}</option>)}</Select>
      </div>
      {metadataError && <p role="alert">{getApiErrorMessage(metadataError, 'Could not load search filters. Reload to retry.')}</p>}
      {state && <details className="rounded-lg border p-3">
        <summary className="cursor-pointer min-h-11 text-sm font-medium">Search area · {suburbs.size ? `${suburbs.size} suburbs selected` : 'Entire state'}</summary>
        <div className="space-y-3 mt-2">
          <Input label="Find a suburb" placeholder="Type a suburb name…" value={locality} onChange={e => setLocality(e.target.value)} />
          <div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => setSuburbs(new Set())}>Clear selection</Button>{!live && <Button variant="secondary" onClick={() => setSuburbs(new Set(available))}>Select entire state</Button>}</div>
          <div className="max-h-64 overflow-y-auto grid sm:grid-cols-2 gap-1">
            {matching.slice(0, 100).map(s => <label key={s} className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={suburbs.has(s)} onChange={() => toggle(s)} />{s}</label>)}
          </div>
          {matching.length > 100 && <p className="text-sm">Showing 100 of {matching.length} suburbs. Type a name to narrow the list.</p>}
          {!matching.length && <p>No suburbs match.</p>}
        </div>
      </details>}
      {suburbs.size > 0 && <div className="flex flex-wrap gap-2">{[...suburbs].slice(0, 8).map(s => <button key={s} className="rounded border px-3 min-h-11 text-sm" onClick={() => toggle(s)} aria-label={`Remove ${s}`}>{s} ×</button>)}{suburbs.size > 8 && <span className="text-sm">+{suburbs.size - 8} more</span>}</div>}
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={live} onChange={e => setLive(e.target.checked)} />Refresh from Google</label>
      <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Stored searches use saved data only. Google refresh covers one result page per area, up to five suburbs. Contact lookups fetch one business at a time.</p>
      {live && suburbs.size > 5 && <p role="alert">Choose up to five suburbs for Google refresh.</p>}
      <Button className="w-full sm:w-auto" disabled={!category || !state || isFetching || (live && suburbs.size > 5)} onClick={search}>{isFetching ? 'Searching…' : 'Search prospects'}</Button>
    </Card>
    {leadsError && <p role="alert">{getApiErrorMessage(leadsError, 'Could not check existing board records. Saving remains safe to retry.')}</p>}
    {isFetching ? <Spinner /> : error ? <div role="alert"><p>{getApiErrorMessage(error)}</p><Button onClick={() => void refetch()}>Retry search</Button></div> : submitted && data ? <>
      <p className="text-sm">{data.total} results · {data.source === 'google' ? 'Google' : 'Stored data'} · {submitted.state}{submitted.suburbs.length ? ` · ${submitted.suburbs.join(', ')}` : ' · statewide search'}</p>
      {data.total > 0 && <Input label="Filter results" placeholder="Business or address…" value={resultFilter} onChange={e => setResultFilter(e.target.value)} />}
      <ul className="space-y-3">{results.map(p => <ProspectResult key={p.place_id} prospect={p} saved={savedIds.has(p.place_id)} state={submitted.state} />)}</ul>
      {!data.total && <p>No {data.source === 'google' ? 'Google' : 'stored'} results for this search. {data.source !== 'google' ? 'Try another area or explicitly refresh from Google.' : 'Try another area or category.'}</p>}
      {data.total > 0 && !results.length && <p>No results match that filter.</p>}
    </> : <p>Choose a category and state to find businesses.</p>}
  </div>
}
