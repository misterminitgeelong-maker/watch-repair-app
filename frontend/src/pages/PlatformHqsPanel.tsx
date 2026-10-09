import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createPlatformHq, getApiErrorMessage, listPlatformHqs, updatePlatformHq, type PlatformHq } from '@/lib/api'
import { Spinner } from '@/components/ui'

const MODULE_LABELS: Record<string, string> = {
  mobile_services: 'Mobile services',
  shoe: 'Shoe repairs',
  watch: 'Watch repairs',
  stock: 'Stock',
  lead_routing: 'Lead routing',
  kpis: 'Mobile KPIs',
  regional_reports: 'Regional reports',
}
const label = (key: string) => MODULE_LABELS[key] ?? key.replace(/_/g, ' ')

function Toggles({ options, value, onChange, name }: { options: string[]; value: string[]; onChange: (v: string[]) => void; name: string }) {
  const flip = (key: string) => onChange(value.includes(key) ? value.filter(k => k !== key) : [...value, key])
  return <div className="flex flex-wrap gap-x-5 gap-y-2" role="group" aria-label={name}>
    {options.map(key => <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={value.includes(key)} onChange={() => flip(key)} />{label(key)}</label>)}
  </div>
}

function HqCard({ hq, modules, plans }: { hq: PlatformHq; modules: string[]; plans: string[] }) {
  const cache = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [displayName, setDisplayName] = useState(hq.display_name)
  const [colour, setColour] = useState(hq.brand_color ?? '')
  const [logo, setLogo] = useState(hq.logo_url ?? '')
  const [mods, setMods] = useState(hq.modules)
  const [sitePlans, setSitePlans] = useState(hq.site_plans)
  const [error, setError] = useState('')
  const save = useMutation({
    mutationFn: () => updatePlatformHq(hq.parent_account_id, { display_name: displayName.trim(), brand_color: colour.trim() || null, logo_url: logo.trim() || null, modules: mods, site_plans: sitePlans }),
    onSuccess: () => { setError(''); setEditing(false); void cache.invalidateQueries({ queryKey: ['platform-hqs'] }) },
    onError: err => setError(getApiErrorMessage(err, 'Could not save this HQ.')),
  })
  return <div className="border-b pb-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <strong>{hq.display_name}</strong>
        <p className="text-sm">Account ID {hq.tenant_slug ?? 'n/a'} · {hq.shop_count} shop{hq.shop_count === 1 ? '' : 's'}</p>
        <p className="text-xs">{hq.modules.length ? hq.modules.map(label).join(', ') : 'No modules on'}</p>
      </div>
      <button className="console-button" onClick={() => setEditing(e => !e)}>{editing ? 'Cancel' : `Edit ${hq.display_name}`}</button>
    </div>
    {editing && <form className="space-y-4 mt-4" onSubmit={e => { e.preventDefault(); setError(''); save.mutate() }}>
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="block text-sm">Display name<input className="block w-full border rounded p-2 mt-1" required maxLength={200} value={displayName} onChange={e => setDisplayName(e.target.value)} /></label>
        <label className="block text-sm">Brand colour<input className="block w-full border rounded p-2 mt-1" placeholder="#1a2b3c" value={colour} onChange={e => setColour(e.target.value)} /></label>
        <label className="block text-sm">Logo URL<input className="block w-full border rounded p-2 mt-1" placeholder="https://…" value={logo} onChange={e => setLogo(e.target.value)} /></label>
      </div>
      <div><p className="text-sm font-medium mb-1">Modules</p><Toggles name="Modules" options={modules} value={mods} onChange={setMods} /></div>
      <div><p className="text-sm font-medium mb-1">Plans this HQ's shops can hold</p><Toggles name="Shop plans" options={plans} value={sitePlans} onChange={setSitePlans} /></div>
      <button className="console-button primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save changes'}</button>
      {error && <p className="console-error" role="alert">{error}</p>}
    </form>}
  </div>
}

export default function PlatformHqsPanel() {
  const cache = useQueryClient()
  const query = useQuery({ queryKey: ['platform-hqs'], queryFn: () => listPlatformHqs().then(r => r.data) })
  const [slug, setSlug] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [ownerEmail, setOwnerEmail] = useState('')
  const [colour, setColour] = useState('')
  const [mods, setMods] = useState<string[]>([])
  const [sitePlans, setSitePlans] = useState<string[]>([])
  const [sendInvite, setSendInvite] = useState(true)
  const [error, setError] = useState('')
  const create = useMutation({
    mutationFn: () => createPlatformHq({ slug: slug.trim().toLowerCase(), display_name: displayName.trim(), brand_color: colour.trim() || null, modules: mods, site_plans: sitePlans, owner_name: ownerName.trim(), owner_email: ownerEmail.trim(), send_invite: sendInvite }).then(r => r.data),
    onSuccess: () => { setError(''); setSlug(''); setDisplayName(''); setOwnerName(''); setOwnerEmail(''); setColour(''); setMods([]); setSitePlans([]); void cache.invalidateQueries({ queryKey: ['platform-hqs'] }); void cache.invalidateQueries({ queryKey: ['platform-hq-owners'] }) },
    onError: err => setError(getApiErrorMessage(err, 'Could not create the HQ.')),
  })
  if (query.isLoading) return <Spinner />
  if (query.isError || !query.data) return <div role="alert">Could not load HQs. <button className="console-button" onClick={() => void query.refetch()}>Try again</button></div>
  const { hqs, available_modules: modules, available_site_plans: plans } = query.data
  return <div className="space-y-5">
    <section className="console-panel">
      <h2>Create an HQ</h2>
      <p className="console-subtitle">Set up a company with many sites. It gets its own network, branding and the modules you switch on, and the owner is invited to take it over. Nothing here touches any other HQ.</p>
      <form className="space-y-4 mt-4" onSubmit={e => { e.preventDefault(); setError(''); create.mutate() }}>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block text-sm">Company name<input className="block w-full border rounded p-2 mt-1" required maxLength={200} value={displayName} onChange={e => setDisplayName(e.target.value)} /></label>
          <label className="block text-sm">Account ID<input className="block w-full border rounded p-2 mt-1" required minLength={3} maxLength={40} placeholder="e.g. birkenstock" value={slug} onChange={e => setSlug(e.target.value)} /></label>
          <label className="block text-sm">Brand colour<input className="block w-full border rounded p-2 mt-1" placeholder="#1a2b3c" value={colour} onChange={e => setColour(e.target.value)} /></label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">Owner name<input className="block w-full border rounded p-2 mt-1" required maxLength={200} value={ownerName} onChange={e => setOwnerName(e.target.value)} /></label>
          <label className="block text-sm">Owner email<input className="block w-full border rounded p-2 mt-1" type="email" required maxLength={254} value={ownerEmail} onChange={e => setOwnerEmail(e.target.value)} /></label>
        </div>
        <div><p className="text-sm font-medium mb-1">New HQ modules</p><Toggles name="New HQ modules" options={modules} value={mods} onChange={setMods} /></div>
        <div><p className="text-sm font-medium mb-1">New HQ shop plans</p><Toggles name="New HQ shop plans" options={plans} value={sitePlans} onChange={setSitePlans} /></div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={sendInvite} onChange={e => setSendInvite(e.target.checked)} />Email the owner their invitation</label>
        <button className="console-button primary" disabled={create.isPending}>{create.isPending ? 'Creating…' : 'Create HQ'}</button>
      </form>
      {error && <p className="console-error mt-4" role="alert">{error}</p>}
      {create.data && <div className="mt-5 space-y-2" role="status">
        <p>{create.data.display_name} is set up.{create.data.email_sent ? ' The owner has been emailed.' : ' Share the invite link below with the owner.'}</p>
        {create.data.invite_url && <label className="block text-sm">Invite link<input className="block w-full border rounded p-2 mt-1" readOnly value={create.data.invite_url} onFocus={e => e.currentTarget.select()} /></label>}
      </div>}
    </section>
    <section className="console-panel"><h2>HQs</h2><div className="mt-3 space-y-4">
      {!hqs.length && <p>No HQs yet.</p>}
      {hqs.map(h => <HqCard key={h.parent_account_id} hq={h} modules={modules} plans={plans} />)}
    </div></section>
  </div>
}
