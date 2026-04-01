import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'
import {
  addCustomerToAccount,
  createCustomerAccount,
  generateCustomerAccountMonthlyInvoice,
  getCustomerAccountStatement,
  getApiErrorMessage,
  listCustomerAccountInvoices,
  listCustomerAccounts,
  listCustomers,
  removeCustomerFromAccount,
  type Customer,
  type CustomerAccountInvoice,
  type CustomerAccountStatement,
} from '@/lib/api'
import { Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner, Textarea } from '@/components/ui'
import { formatDate } from '@/lib/utils'

function CreateCustomerAccountModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    name: '',
    account_code: '',
    contact_name: '',
    contact_email: '',
    contact_phone: '',
    billing_address: '',
    payment_terms_days: '30',
    notes: '',
    // Fleet/Dealer fields
    account_type: '',
    fleet_size: '',
    primary_contact_name: '',
    primary_contact_phone: '',
    billing_cycle: '',
    credit_limit: '',
    account_notes: '',
  })
  const createMut = useMutation({
    mutationFn: () => createCustomerAccount({
      name: form.name.trim(),
      account_code: form.account_code.trim() || undefined,
      contact_name: form.contact_name.trim() || undefined,
      contact_email: form.contact_email.trim() || undefined,
      contact_phone: form.contact_phone.trim() || undefined,
      billing_address: form.billing_address.trim() || undefined,
      payment_terms_days: form.payment_terms_days ? parseInt(form.payment_terms_days, 10) : undefined,
      notes: form.notes.trim() || undefined,
      account_type: form.account_type || undefined,
      fleet_size: form.fleet_size ? parseInt(form.fleet_size, 10) : undefined,
      primary_contact_name: form.primary_contact_name.trim() || undefined,
      primary_contact_phone: form.primary_contact_phone.trim() || undefined,
      billing_cycle: form.billing_cycle || undefined,
      credit_limit: form.credit_limit ? parseInt(form.credit_limit, 10) : undefined,
      account_notes: form.account_notes.trim() || undefined,
    } as Parameters<typeof createCustomerAccount>[0]),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['customer-accounts'] }); onClose(); },
    onError: (err) => setError(getApiErrorMessage(err, 'Failed to create account.')),
  })
  return (
    <Modal title="Create Customer Account" onClose={onClose}>
      <div className="space-y-3">
        <Input label="Account name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} maxLength={128} />
        <Input label="Account code" value={form.account_code} onChange={e => setForm(f => ({ ...f, account_code: e.target.value }))} maxLength={32} />
        <Input label="Contact name" value={form.contact_name} onChange={e => setForm(f => ({ ...f, contact_name: e.target.value }))} maxLength={64} />
        <Input label="Contact phone" value={form.contact_phone} onChange={e => setForm(f => ({ ...f, contact_phone: e.target.value }))} maxLength={32} />
        <Input label="Contact email" type="email" value={form.contact_email} onChange={e => setForm(f => ({ ...f, contact_email: e.target.value }))} maxLength={64} />
        <Textarea label="Billing address" value={form.billing_address} onChange={e => setForm(f => ({ ...f, billing_address: e.target.value }))} rows={2} maxLength={256} />
        <Input label="Payment terms (days)" type="number" min="0" value={form.payment_terms_days} onChange={e => setForm(f => ({ ...f, payment_terms_days: e.target.value }))} />
        <Textarea label="Notes" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} maxLength={256} />

        {/* Fleet/Dealer/Subscription fields */}
        <Select label="Account type" value={form.account_type} onChange={e => setForm(f => ({ ...f, account_type: e.target.value }))}>
          <option value="">Select type</option>
          <option value="Dealership">Dealership</option>
          <option value="Rental Fleet">Rental Fleet</option>
          <option value="Government Fleet">Government Fleet</option>
          <option value="Corporate Fleet">Corporate Fleet</option>
          <option value="Car Auctions">Car Auctions</option>
          <option value="Other">Other</option>
        </Select>
        <Input label="Fleet size (vehicles)" type="number" min="0" value={form.fleet_size} onChange={e => setForm(f => ({ ...f, fleet_size: e.target.value }))} />
        <div className="grid grid-cols-2 gap-3">
          <Input label="Primary contact name" value={form.primary_contact_name} onChange={e => setForm(f => ({ ...f, primary_contact_name: e.target.value }))} maxLength={64} />
          <Input label="Primary contact phone" value={form.primary_contact_phone} onChange={e => setForm(f => ({ ...f, primary_contact_phone: e.target.value }))} maxLength={32} />
        </div>
        <Select label="Billing cycle" value={form.billing_cycle} onChange={e => setForm(f => ({ ...f, billing_cycle: e.target.value }))}>
          <option value="">Select cycle</option>
          <option value="Monthly">Monthly</option>
          <option value="Fortnightly">Fortnightly</option>
          <option value="Weekly">Weekly</option>
        </Select>
        <Input label="Credit limit ($)" type="number" min="0" value={form.credit_limit} onChange={e => setForm(f => ({ ...f, credit_limit: e.target.value }))} />
        <Textarea label="Account notes" value={form.account_notes} onChange={e => setForm(f => ({ ...f, account_notes: e.target.value }))} rows={2} maxLength={256} />

        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}

        <div className="flex gap-2 pt-2">
          <Button variant="secondary" className="flex-1" onClick={onClose}>Cancel</Button>
          <Button className="flex-1" onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.name.trim()}>
            {createMut.isPending ? 'Creating…' : 'Create Account'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default function CustomerAccountsPage() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [selectedCustomerByAccount, setSelectedCustomerByAccount] = useState<Record<string, string>>({})
  const [periodByAccount, setPeriodByAccount] = useState<Record<string, string>>({})
  const [taxByAccount, setTaxByAccount] = useState<Record<string, string>>({})
  const [statementByAccount, setStatementByAccount] = useState<Record<string, CustomerAccountStatement>>({})
  const [latestInvoiceByAccount, setLatestInvoiceByAccount] = useState<Record<string, CustomerAccountInvoice>>({})
  const [invoiceListByAccount, setInvoiceListByAccount] = useState<Record<string, CustomerAccountInvoice[]>>({})
  const [expandedInvoiceById, setExpandedInvoiceById] = useState<Record<string, boolean>>({})
  const [billingErrorByAccount, setBillingErrorByAccount] = useState<Record<string, string>>({})

  const { data: accounts = [], isLoading, isError, error, refetch } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
    retry: 0,
    staleTime: 0,
  })

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers().then(r => r.data),
  })

  const addMut = useMutation({
    mutationFn: ({ accountId, customerId }: { accountId: string; customerId: string }) => addCustomerToAccount(accountId, customerId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['customer-accounts'] }),
  })

  const removeMut = useMutation({
    mutationFn: ({ accountId, customerId }: { accountId: string; customerId: string }) => removeCustomerFromAccount(accountId, customerId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['customer-accounts'] }),
  })

  const previewMut = useMutation({
    mutationFn: ({ accountId, year, month }: { accountId: string; year: number; month: number }) =>
      getCustomerAccountStatement(accountId, year, month),
    onSuccess: (res, vars) => {
      setBillingErrorByAccount(prev => ({ ...prev, [vars.accountId]: '' }))
      setStatementByAccount(prev => ({ ...prev, [vars.accountId]: res.data }))
    },
    onError: (err, vars) => {
      setBillingErrorByAccount(prev => ({
        ...prev,
        [vars.accountId]: getApiErrorMessage(err, 'Failed to preview statement.'),
      }))
    },
  })

  const generateMut = useMutation({
    mutationFn: ({ accountId, year, month, taxCents }: { accountId: string; year: number; month: number; taxCents: number }) =>
      generateCustomerAccountMonthlyInvoice(accountId, {
        period_year: year,
        period_month: month,
        tax_cents: taxCents,
      }),
    onSuccess: async (res, vars) => {
      setBillingErrorByAccount(prev => ({ ...prev, [vars.accountId]: '' }))
      setLatestInvoiceByAccount(prev => ({ ...prev, [vars.accountId]: res.data }))
      const invoiceRes = await listCustomerAccountInvoices(vars.accountId)
      setInvoiceListByAccount(prev => ({ ...prev, [vars.accountId]: invoiceRes.data }))
    },
    onError: (err, vars) => {
      setBillingErrorByAccount(prev => ({
        ...prev,
        [vars.accountId]: getApiErrorMessage(err, 'Failed to generate monthly invoice.'),
      }))
    },
  })

  const fetchInvoicesMut = useMutation({
    mutationFn: (accountId: string) => listCustomerAccountInvoices(accountId),
    onSuccess: (res, accountId) => {
      setBillingErrorByAccount(prev => ({ ...prev, [accountId]: '' }))
      setInvoiceListByAccount(prev => ({ ...prev, [accountId]: res.data }))
    },
    onError: (err, accountId) => {
      setBillingErrorByAccount(prev => ({
        ...prev,
        [accountId]: getApiErrorMessage(err, 'Failed to load invoice history.'),
      }))
    },
  })

  useEffect(() => {
    const missingAccountIds = accounts
      .map((account) => account.id)
      .filter((accountId) => invoiceListByAccount[accountId] === undefined)
    if (missingAccountIds.length === 0) return

    let canceled = false
    void Promise.all(
      missingAccountIds.map(async (accountId) => {
        try {
          const res = await listCustomerAccountInvoices(accountId)
          return { accountId, invoices: res.data, error: '' }
        } catch (err) {
          return {
            accountId,
            invoices: [] as CustomerAccountInvoice[],
            error: getApiErrorMessage(err, 'Failed to load invoice history.'),
          }
        }
      })
    ).then((results) => {
      if (canceled) return
      setInvoiceListByAccount((prev) => {
        const next = { ...prev }
        for (const result of results) next[result.accountId] = result.invoices
        return next
      })
      setBillingErrorByAccount((prev) => {
        const next = { ...prev }
        for (const result of results) {
          if (result.error) next[result.accountId] = result.error
        }
        return next
      })
    })

    return () => {
      canceled = true
    }
  }, [accounts, invoiceListByAccount])

  function customerName(id: string) {
    return customers.find((c: Customer) => c.id === id)?.full_name ?? id
  }

  function centsToCurrency(cents: number) {
    return `$${(cents / 100).toFixed(2)}`
  }

  function periodValueFor(accountId: string) {
    if (periodByAccount[accountId]) return periodByAccount[accountId]
    const now = new Date()
    const y = now.getFullYear()
    const m = String(now.getMonth() + 1).padStart(2, '0')
    return `${y}-${m}`
  }

  function parsePeriod(value: string) {
    const [y, m] = value.split('-')
    return { year: Number(y), month: Number(m) }
  }

  function sourceLabel(source: 'watch' | 'shoe' | 'auto_key') {
    if (source === 'auto_key') return 'Mobile Services'
    if (source === 'shoe') return 'Shoe'
    return 'Watch'
  }

  function toCsvCell(value: string | number) {
    const text = String(value)
    if (text.includes(',') || text.includes('"') || text.includes('\n')) {
      return `"${text.replace(/"/g, '""')}"`
    }
    return text
  }

  function downloadInvoiceCsv(accountName: string, invoices: CustomerAccountInvoice[]) {
    if (invoices.length === 0) return
    const header = [
      'invoice_number',
      'period_year',
      'period_month',
      'status',
      'subtotal_cents',
      'tax_cents',
      'total_cents',
      'source_type',
      'job_number',
      'description',
      'line_amount_cents',
      'created_at',
    ]
    const rows: string[] = [header.map(toCsvCell).join(',')]

    for (const invoice of invoices) {
      if (invoice.lines.length === 0) {
        rows.push([
          invoice.invoice_number,
          invoice.period_year,
          invoice.period_month,
          invoice.status,
          invoice.subtotal_cents,
          invoice.tax_cents,
          invoice.total_cents,
          '',
          '',
          '',
          '',
          invoice.created_at,
        ].map(toCsvCell).join(','))
        continue
      }

      for (const line of invoice.lines) {
        rows.push([
          invoice.invoice_number,
          invoice.period_year,
          invoice.period_month,
          invoice.status,
          invoice.subtotal_cents,
          invoice.tax_cents,
          invoice.total_cents,
          line.source_type,
          line.job_number,
          line.description,
          line.amount_cents,
          invoice.created_at,
        ].map(toCsvCell).join(','))
      }
    }

    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const safeName = accountName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'customer-account'
    const a = document.createElement('a')
    a.href = url
    a.download = `${safeName}-invoices.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  function jobPath(source: 'watch' | 'shoe' | 'auto_key', jobId: string) {
    if (source === 'shoe') return `/shoe-repairs/${jobId}`
    if (source === 'auto_key') return `/auto-key/${jobId}`
    return `/jobs/${jobId}`
  }

  function computeAccountSummary(invoices: CustomerAccountInvoice[]) {
    const now = new Date()
    const currentYear = now.getFullYear()
    const currentMonth = now.getMonth() + 1
    const monthlyInvoices = invoices.filter(
      (inv) => inv.period_year === currentYear && inv.period_month === currentMonth
    )

    const monthlyJobIds = new Set<string>()
    for (const invoice of monthlyInvoices) {
      for (const line of invoice.lines) monthlyJobIds.add(line.source_job_id)
    }

    const totalInvoicedThisMonthCents = monthlyInvoices.reduce((sum, inv) => sum + inv.total_cents, 0)
    const outstandingBalanceCents = invoices
      .filter((inv) => inv.status !== 'paid')
      .reduce((sum, inv) => sum + inv.total_cents, 0)

    return {
      totalJobsThisMonth: monthlyJobIds.size,
      totalInvoicedThisMonthCents,
      outstandingBalanceCents,
    }
  }

  // Dashboard summary calculations
  const fleetAccounts = accounts.filter(a => a.account_type)
  const totalFleet = fleetAccounts.length
  const totalCreditLimit = fleetAccounts.reduce((sum, a) => sum + (a.credit_limit || 0), 0)
  const billingCycleCounts = fleetAccounts.reduce((acc, a) => {
    if (a.billing_cycle) acc[a.billing_cycle] = (acc[a.billing_cycle] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <div>
      <PageHeader title="Customer Accounts (B2B)" action={<Button onClick={() => setShowCreate(true)}><Plus size={16} />Create Account</Button>} />

      {/* Dashboard summary */}
      <div className="mb-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border p-4" style={{ borderColor: 'var(--cafe-border)', backgroundColor: '#F8F5EE' }}>
          <div className="text-xs font-semibold uppercase mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Active Fleet/Dealer Accounts</div>
          <div className="text-2xl font-bold" style={{ color: 'var(--cafe-text)' }}>{totalFleet}</div>
        </div>
        <div className="rounded-lg border p-4" style={{ borderColor: 'var(--cafe-border)', backgroundColor: '#F8F5EE' }}>
          <div className="text-xs font-semibold uppercase mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Total Credit Limit</div>
          <div className="text-2xl font-bold" style={{ color: 'var(--cafe-text)' }}>${totalCreditLimit.toLocaleString()}</div>
        </div>
        <div className="rounded-lg border p-4" style={{ borderColor: 'var(--cafe-border)', backgroundColor: '#F8F5EE' }}>
          <div className="text-xs font-semibold uppercase mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Billing Cycle Distribution</div>
          <ul className="text-sm mt-1">
            {Object.entries(billingCycleCounts).length === 0 && <li style={{ color: 'var(--cafe-text-muted)' }}>None</li>}
            {Object.entries(billingCycleCounts).map(([cycle, count]) => (
              <li key={cycle}><span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{cycle}</span>: {count}</li>
            ))}
          </ul>
        </div>
      </div>

      {showCreate && <CreateCustomerAccountModal onClose={() => setShowCreate(false)} />}

      {isError ? (
        <div className="rounded-lg border p-4" style={{ borderColor: '#C96A5A', backgroundColor: '#FDF2F0' }}>
          <p className="text-sm font-semibold" style={{ color: '#C96A5A' }}>Could not load customer accounts</p>
          <p className="text-xs mt-1" style={{ color: '#5F4734' }}>
            {getApiErrorMessage(error as unknown, 'Request timed out or failed')}
          </p>
          <Button className="mt-3" onClick={() => refetch()}>Try again</Button>
        </div>
      ) : isLoading ? (
        <Spinner />
      ) : accounts.length === 0 ? (
        <EmptyState message="No customer accounts yet." />
      ) : (
        <div className="space-y-3">
          {accounts.map(account => {
            const selectedCustomer = selectedCustomerByAccount[account.id] ?? ''
            const periodValue = periodValueFor(account.id)
            const { year, month } = parsePeriod(periodValue)
            const statement = statementByAccount[account.id]
            const latestInvoice = latestInvoiceByAccount[account.id]
            const history = invoiceListByAccount[account.id] ?? []
            const summary = computeAccountSummary(history)
            const available = customers.filter(c => !account.customer_ids.includes(c.id))
            return (
              <Card key={account.id} className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold" style={{ color: 'var(--cafe-text)' }}>{account.name}</p>
                    <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                      {account.account_code ? `Code ${account.account_code} · ` : ''}
                      Terms {account.payment_terms_days} days
                      {account.contact_email ? ` · ${account.contact_email}` : ''}
                    </p>
                    {/* Fleet/Dealer fields summary */}
                    <div className="mt-1 grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-1 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                      {account.account_type && <div>Type: <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{account.account_type}</span></div>}
                      {account.fleet_size !== undefined && account.fleet_size !== null && <div>Fleet size: <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{account.fleet_size}</span></div>}
                      {account.primary_contact_name && <div>Primary contact: <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{account.primary_contact_name}</span></div>}
                      {account.primary_contact_phone && <div>Contact phone: <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{account.primary_contact_phone}</span></div>}
                      {account.billing_cycle && <div>Billing cycle: <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{account.billing_cycle}</span></div>}
                      {account.credit_limit !== undefined && account.credit_limit !== null && <div>Credit limit: <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>${account.credit_limit}</span></div>}
                    </div>
                    {account.account_notes && <p className="text-xs mt-1" style={{ color: 'var(--cafe-text-muted)' }}>{account.account_notes}</p>}
                    {account.notes && <p className="text-xs mt-1" style={{ color: 'var(--cafe-text-muted)' }}>{account.notes}</p>}
                  </div>
                </div>


                <div className="mt-3 rounded-lg border p-3" style={{ borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}>
                  <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>
                    Linked customers ({account.customer_ids.length})
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {account.customer_ids.length === 0 ? (
                      <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>No customers linked yet.</p>
                    ) : account.customer_ids.map(customerId => (
                      <span key={customerId} className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs" style={{ backgroundColor: '#EFE9DF', color: '#5F4734' }}>
                        {customerName(customerId)}
                        <button
                          onClick={() => removeMut.mutate({ accountId: account.id, customerId })}
                          className="ml-1"
                          disabled={removeMut.isPending}
                          aria-label="Remove customer"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Select
                      value={selectedCustomer}
                      onChange={e => setSelectedCustomerByAccount(prev => ({ ...prev, [account.id]: e.target.value }))}
                      className="flex-1"
                    >
                      <option value="">Add customer…</option>
                      {available.map(c => <option key={c.id} value={c.id}>{c.full_name}</option>)}
                    </Select>
                    <Button
                      onClick={() => selectedCustomer && addMut.mutate({ accountId: account.id, customerId: selectedCustomer })}
                      disabled={!selectedCustomer || addMut.isPending}
                    >
                      Add
                    </Button>
                  </div>
                </div>

                <div className="mt-3 rounded-lg border p-3" style={{ borderColor: 'var(--cafe-border)', backgroundColor: '#F8F5EE' }}>
                  <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>
                    Month-End Billing
                  </p>
                  <div className="mt-2 grid gap-2 md:grid-cols-3">
                    <Input
                      label="Billing month"
                      type="month"
                      value={periodValue}
                      onChange={e => setPeriodByAccount(prev => ({ ...prev, [account.id]: e.target.value }))}
                    />
                    <Input
                      label="Tax ($)"
                      type="number"
                      min="0"
                      step="0.01"
                      value={taxByAccount[account.id] ?? '0'}
                      onChange={e => setTaxByAccount(prev => ({ ...prev, [account.id]: e.target.value }))}
                    />
                    <div className="flex gap-2 items-end">
                      <Button
                        variant="secondary"
                        className="flex-1"
                        onClick={() => previewMut.mutate({ accountId: account.id, year, month })}
                        disabled={previewMut.isPending}
                      >
                        Preview Statement
                      </Button>
                      <Button
                        className="flex-1"
                        onClick={() => {
                          const taxDollars = Number(taxByAccount[account.id] ?? '0')
                          const taxCents = Number.isFinite(taxDollars) ? Math.max(0, Math.round(taxDollars * 100)) : 0
                          generateMut.mutate({ accountId: account.id, year, month, taxCents })
                        }}
                        disabled={generateMut.isPending}
                      >
                        Generate Invoice
                      </Button>
                    </div>
                  </div>

                  {billingErrorByAccount[account.id] && (
                    <p className="mt-2 text-xs" style={{ color: '#C96A5A' }}>{billingErrorByAccount[account.id]}</p>
                  )}

                  {statement && (
                    <div className="mt-3 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                      <p>
                        Statement: {statement.lines.length} line{statement.lines.length === 1 ? '' : 's'} · Subtotal {centsToCurrency(statement.subtotal_cents)}
                      </p>
                    </div>
                  )}

                  {latestInvoice && (
                    <div className="mt-2 rounded border p-2 text-xs" style={{ borderColor: 'var(--cafe-border)', color: 'var(--cafe-text-muted)' }}>
                      Created invoice {latestInvoice.invoice_number} · Total {centsToCurrency(latestInvoice.total_cents)}
                    </div>
                  )}

                  {history.length > 0 && (
                    <div className="mt-3 rounded border" style={{ borderColor: 'var(--cafe-border)', backgroundColor: '#FFFDF9' }}>
                      <div className="flex items-center justify-between px-2.5 py-2 text-xs" style={{ borderBottom: '1px solid var(--cafe-border)', color: 'var(--cafe-text-muted)' }}>
                        <span>Recent invoices</span>
                        <span>{history.length}</span>
                      </div>
                      <div>
                        {history.slice(0, 5).map(inv => (
                          <div key={inv.id} className="px-2.5 py-2 text-xs" style={{ borderBottom: '1px solid var(--cafe-border)', color: 'var(--cafe-text-muted)' }}>
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <p className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{inv.invoice_number}</p>
                                <p>{inv.period_year}-{String(inv.period_month).padStart(2, '0')} · {formatDate(inv.created_at)}</p>
                              </div>
                              <div className="text-right">
                                <p className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{centsToCurrency(inv.total_cents)}</p>
                                <p className="capitalize">{inv.status}</p>
                              </div>
                            </div>

                            <div className="mt-1.5 flex justify-end">
                              <button
                                type="button"
                                className="text-[11px] font-semibold"
                                style={{ color: 'var(--cafe-amber)' }}
                                onClick={() => setExpandedInvoiceById(prev => ({ ...prev, [inv.id]: !prev[inv.id] }))}
                              >
                                {expandedInvoiceById[inv.id] ? 'Hide lines' : `View lines (${inv.lines.length})`}
                              </button>
                            </div>

                            {expandedInvoiceById[inv.id] && (
                              <div className="mt-2 rounded border" style={{ borderColor: 'var(--cafe-border)', backgroundColor: '#FFFFFF' }}>
                                {inv.lines.length === 0 ? (
                                  <p className="px-2 py-2 text-[11px]" style={{ color: 'var(--cafe-text-muted)' }}>No lines in this invoice.</p>
                                ) : (
                                  inv.lines.map((line) => (
                                    <div key={`${inv.id}-${line.source_job_id}`} className="px-2 py-1.5 flex items-start justify-between gap-2 text-[11px]" style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                                      <div>
                                        <Link
                                          to={jobPath(line.source_type, line.source_job_id)}
                                          className="font-semibold hover:underline"
                                          style={{ color: 'var(--cafe-text)' }}
                                        >
                                          {sourceLabel(line.source_type)} · #{line.job_number}
                                        </Link>
                                        <p style={{ color: 'var(--cafe-text-muted)' }}>{line.description}</p>
                                      </div>
                                      <p className="font-semibold whitespace-nowrap" style={{ color: 'var(--cafe-text)' }}>
                                        {centsToCurrency(line.amount_cents)}
                                      </p>
                                    </div>
                                  ))
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="mt-2 flex justify-end">
                    <div className="flex gap-2">
                      {history.length > 0 && (
                        <Button
                          variant="secondary"
                          onClick={() => downloadInvoiceCsv(account.name, history)}
                        >
                          Export CSV
                        </Button>
                      )}
                      <Button
                        variant="secondary"
                        onClick={() => fetchInvoicesMut.mutate(account.id)}
                        disabled={fetchInvoicesMut.isPending}
                      >
                        {fetchInvoicesMut.isPending ? 'Loading…' : history.length > 0 ? 'Refresh Invoices' : 'Load Invoices'}
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
