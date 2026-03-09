import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { listCustomers, createCustomer, type Customer } from '@/lib/api'
import { Card, PageHeader, Button, Input, Modal, Spinner, EmptyState, Textarea } from '@/components/ui'
import { formatDate } from '@/lib/utils'

function AddCustomerModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [form, setForm] = useState({ full_name: '', email: '', phone: '', notes: '' })
  const [error, setError] = useState('')
  const mut = useMutation({
    mutationFn: () => createCustomer(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['customers'] }); onClose() },
    onError: () => setError('Failed to create customer.'),
  })
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  return (
    <Modal title="New Customer" onClose={onClose}>
      <div className="space-y-3">
        <Input label="Full Name *" value={form.full_name} onChange={set('full_name')} placeholder="Jane Smith" required />
        <Input label="Email" type="email" value={form.email} onChange={set('email')} placeholder="jane@example.com" />
        <Input label="Phone" value={form.phone} onChange={set('phone')} placeholder="+1 555 000 0000" />
        <Textarea label="Notes" value={form.notes} onChange={set('notes')} rows={2} placeholder="VIP client, allergic to…" />
        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={!form.full_name || mut.isPending}>
            {mut.isPending ? 'Saving…' : 'Add Customer'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default function CustomersPage() {
  const [showAdd, setShowAdd] = useState(false)
  const [search, setSearch] = useState('')
  const { data: customers, isLoading } = useQuery({ queryKey: ['customers'], queryFn: () => listCustomers().then(r => r.data) })

  const filtered = (customers ?? []).filter(c =>
    c.full_name.toLowerCase().includes(search.toLowerCase()) ||
    c.email?.toLowerCase().includes(search.toLowerCase()) ||
    c.phone?.includes(search)
  )

  return (
    <div>
      <PageHeader title="Customers" action={<Button onClick={() => setShowAdd(true)}><Plus size={16} />Add Customer</Button>} />
      {showAdd && <AddCustomerModal onClose={() => setShowAdd(false)} />}

      <div className="mb-5 relative max-w-xs">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--cafe-text-muted)' }} />
        <input
          className="w-full pl-9 pr-4 py-2 rounded-lg text-sm outline-none transition"
          style={{
            backgroundColor: 'var(--cafe-surface)',
            border: '1px solid var(--cafe-border-2)',
            color: 'var(--cafe-text)',
          }}
          placeholder="Search customers…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? <Spinner /> : (
        <Card>
          {filtered.length === 0 ? <EmptyState message="No customers found." /> : (
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  {['Name', 'Email', 'Phone', 'Added'].map(h => (
                    <th
                      key={h}
                      className="px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase"
                      style={{ color: 'var(--cafe-text-muted)' }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((c: Customer, i) => (
                  <tr
                    key={c.id}
                    style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td className="px-5 py-3.5">
                      <Link
                        to={`/customers/${c.id}`}
                        className="font-medium hover:underline"
                        style={{ color: 'var(--cafe-amber)' }}
                      >
                        {c.full_name}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{c.email ?? '—'}</td>
                    <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{c.phone ?? '—'}</td>
                    <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-muted)' }}>{formatDate(c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  )
}
