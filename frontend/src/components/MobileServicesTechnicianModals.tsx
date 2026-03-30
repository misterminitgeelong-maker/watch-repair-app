import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  buildMobileCommissionRulesJson,
  createUser,
  getApiErrorMessage,
  isDuplicateTenantUserEmailError,
  listUsers,
  updateUser,
} from '@/lib/api'
import { Button, Input, Modal, Select } from '@/components/ui'

export function AddTechnicianModal({
  onClose,
  onAdded,
}: {
  onClose: () => void
  onAdded?: () => void
}) {
  const qc = useQueryClient()
  const [form, setForm] = useState({ full_name: '', email: '', password: '' })
  const [commEnabled, setCommEnabled] = useState(true)
  const [retainerDollars, setRetainerDollars] = useState('360')
  const [shopPct, setShopPct] = useState('30')
  const [selfPct, setSelfPct] = useState('50')
  const [error, setError] = useState<string | 'duplicate_email' | null>(null)
  const mut = useMutation({
    mutationFn: () =>
      createUser({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
        role: 'tech',
        mobile_commission_rules_json: commEnabled
          ? buildMobileCommissionRulesJson({
              enabled: true,
              retainerDollars: Math.max(0, parseFloat(retainerDollars) || 0),
              shopPercent: Math.max(0, parseFloat(shopPct) || 0),
              techSourcedPercent: Math.max(0, parseFloat(selfPct) || 0),
            })
          : undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      onAdded?.()
      onClose()
    },
    onError: (err: unknown) => {
      if (isDuplicateTenantUserEmailError(err)) {
        setError('duplicate_email')
        return
      }
      setError(getApiErrorMessage(err, 'Could not add technician. Only owners can add accounts; check plan limits.'))
    },
  })
  return (
    <Modal title="Add technician" onClose={onClose}>
      <p className="text-sm mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
        Creates a login they can use in the app. Assign them to jobs from the job page or dispatch views.
      </p>
      <div className="space-y-3">
        <Input label="Full name *" value={form.full_name} onChange={e => { setError(null); setForm(f => ({ ...f, full_name: e.target.value })) }} placeholder="Alex Smith" autoFocus />
        <Input label="Email *" type="email" value={form.email} onChange={e => { setError(null); setForm(f => ({ ...f, email: e.target.value })) }} placeholder="alex@shop.com" />
        <Input label="Password *" type="password" value={form.password} onChange={e => { setError(null); setForm(f => ({ ...f, password: e.target.value })) }} placeholder="At least 8 characters" />
        <div className="rounded-xl border p-3 space-y-3" style={{ borderColor: 'var(--cafe-border-2)', backgroundColor: 'var(--cafe-bg)' }}>
          <label className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: 'var(--cafe-text)' }}>
            <input type="checkbox" checked={commEnabled} onChange={e => setCommEnabled(e.target.checked)} />
            Mobile Services commission tracking (bonus above retainer)
          </label>
          {commEnabled && (
            <>
              <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                First portion of commission each period counts toward salary (retainer); only the amount above that is bonus. Percentages apply to invoice total. You can change keys or add tiers later under Commission rules.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <Input label="Retainer ($ / period)" value={retainerDollars} onChange={e => setRetainerDollars(e.target.value)} />
                <Input label="Shop / referred %" value={shopPct} onChange={e => setShopPct(e.target.value)} />
                <Input label="Tech sourced %" value={selfPct} onChange={e => setSelfPct(e.target.value)} />
              </div>
            </>
          )}
        </div>
        {error === 'duplicate_email' && (
          <div className="text-sm space-y-2 rounded-lg border px-3 py-2" style={{ borderColor: 'var(--cafe-border-2)', color: '#C96A5A' }}>
            <p className="font-medium" style={{ color: 'var(--cafe-text)' }}>This email is already on your team</p>
            <p style={{ color: 'var(--cafe-text-muted)' }}>
              Each address can only be used once. If you already added this technician, open{' '}
              <Link to="/auto-key/team" className="font-medium underline" style={{ color: 'var(--cafe-amber)' }} onClick={onClose}>Team</Link>
              {' to confirm they are listed. To change their password or role, use '}
              <Link to="/accounts" className="font-medium underline" style={{ color: 'var(--cafe-amber)' }} onClick={onClose}>Team accounts</Link>.
            </p>
          </div>
        )}
        {error && error !== 'duplicate_email' && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>Cancel</Button>
          <Button
            type="button"
            onClick={() => { setError(null); mut.mutate() }}
            disabled={mut.isPending || !form.full_name.trim() || !form.email.trim() || form.password.length < 8}
          >
            {mut.isPending ? 'Adding…' : 'Add technician'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export function MobileCommissionRulesModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers().then(r => r.data),
  })
  const techs = users.filter(u => u.role === 'tech')
  const [userId, setUserId] = useState('')
  const [enabled, setEnabled] = useState(false)
  const [retainer, setRetainer] = useState('360')
  const [shop, setShop] = useState('30')
  const [self, setSelf] = useState('50')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!userId && techs.length) setUserId(techs[0].id)
  }, [techs, userId])

  useEffect(() => {
    const u = techs.find(t => t.id === userId)
    const raw = u?.mobile_commission_rules_json
    if (!raw) {
      setEnabled(false)
      setRetainer('360')
      setShop('30')
      setSelf('50')
      return
    }
    try {
      const r = JSON.parse(raw) as {
        enabled?: boolean
        retainer_cents_per_period?: number
        rates_bp?: { shop_referred?: number; tech_sourced?: number }
      }
      setEnabled(Boolean(r.enabled))
      setRetainer(String((r.retainer_cents_per_period ?? 36_000) / 100))
      setShop(String((r.rates_bp?.shop_referred ?? 3000) / 100))
      setSelf(String((r.rates_bp?.tech_sourced ?? 5000) / 100))
    } catch {
      setEnabled(false)
    }
  }, [userId, techs])

  const mut = useMutation({
    mutationFn: async () => {
      if (!userId) throw new Error('Select a technician.')
      if (enabled) {
        const json = buildMobileCommissionRulesJson({
          enabled: true,
          retainerDollars: Math.max(0, parseFloat(retainer) || 0),
          shopPercent: Math.max(0, parseFloat(shop) || 0),
          techSourcedPercent: Math.max(0, parseFloat(self) || 0),
        })
        await updateUser(userId, { mobile_commission_rules_json: json })
      } else {
        await updateUser(userId, { mobile_commission_rules_json: '' })
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: (err: unknown) => setError(getApiErrorMessage(err, 'Could not save rules.')),
  })

  return (
    <Modal title="Mobile Services commission rules" onClose={onClose}>
      <p className="text-sm mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
        Rules are stored as JSON on each technician (extend with custom <code className="text-xs">rates_bp</code> keys and matching job <strong>lead source</strong> on each job). Default keys: shop_referred, tech_sourced.
      </p>
      {techs.length === 0 ? (
        <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
          No technicians yet. Add one from Team or the main Mobile Services page first.
        </p>
      ) : (
        <div className="space-y-3">
          <Select label="Technician" value={userId} onChange={e => setUserId(e.target.value)}>
            {techs.map(t => (
              <option key={t.id} value={t.id}>{t.full_name}</option>
            ))}
          </Select>
          <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--cafe-text)' }}>
            <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />
            Commission tracking enabled
          </label>
          {enabled && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <Input label="Retainer ($)" value={retainer} onChange={e => setRetainer(e.target.value)} />
              <Input label="Shop / referred %" value={shop} onChange={e => setShop(e.target.value)} />
              <Input label="Tech sourced %" value={self} onChange={e => setSelf(e.target.value)} />
            </div>
          )}
        </div>
      )}
      {error && <p className="text-sm mt-2" style={{ color: '#C96A5A' }}>{error}</p>}
      <div className="flex justify-end gap-2 pt-4">
        <Button variant="secondary" type="button" onClick={onClose}>Cancel</Button>
        <Button type="button" disabled={!techs.length || mut.isPending} onClick={() => { setError(''); mut.mutate() }}>
          {mut.isPending ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </Modal>
  )
}
