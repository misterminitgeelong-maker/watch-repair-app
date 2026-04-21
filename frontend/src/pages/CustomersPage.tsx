import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { DEFAULT_PAGE_SIZE, listCustomers, createCustomer, getApiErrorMessage, type Customer, type SortDir } from '@/lib/api'
import { Card, PageHeader, Button, Input, Modal, Spinner, EmptyState, Textarea } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import { flattenInfinitePages, useOffsetPaginatedQuery } from '@/hooks/useOffsetPaginatedQuery'

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
  const [sortBy, setSortBy] = useState<'created_at' | 'full_name'>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const customersQuery = useOffsetPaginatedQuery({
    queryKey: ['customers', 'paged', sortBy, sortDir],
    queryFn: (offset) =>
      listCustomers({
        limit: DEFAULT_PAGE_SIZE,
        offset,
        sort_by: sortBy,
        sort_dir: sortDir,
      }).then((r) => r.data),
  })

  const customers = useMemo(() => flattenInfinitePages(customersQuery.data), [customersQuery.data])
  const isLoading = customersQuery.isLoading

  const filtered = customers.filter(c =>
    c.full_name.toLowerCase().includes(search.toLowerCase()) ||
    c.email?.toLowerCase().includes(search.toLowerCase()) ||
    c.phone?.includes(search)
  )

  return (
    <div>
      <PageHeader title="Customers" action={<Button onClick={() => setShowAdd(true)}><Plus size={16} />Add Customer</Button>} />
      {showAdd && <AddCustomerModal onClose={() => setShowAdd(false)} />}

      <div className="mb-5 flex flex-wrap gap-3 items-end">
        <div className="relative w-full max-w-md flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ms-text-muted)' }} />
          <input
            className="w-full pl-9 pr-4 py-2.5 rounded-lg text-base sm:text-sm outline-none transition"
            style={{
              backgroundColor: 'var(--ms-surface)',
              border: '1px solid var(--ms-border-strong)',
              color: 'var(--ms-text)',
            }}
            placeholder="Search customers…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <select
          className="rounded-lg px-3 py-2.5 text-sm outline-none transition"
          style={{
            backgroundColor: 'var(--ms-surface)',
            border: '1px solid var(--ms-border-strong)',
            color: 'var(--ms-text)',
          }}
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as 'created_at' | 'full_name')}
          aria-label="Sort customers"
        >
          <option value="created_at">Sort: Date added</option>
          <option value="full_name">Sort: Name</option>
        </select>
        <select
          className="rounded-lg px-3 py-2.5 text-sm outline-none transition"
          style={{
            backgroundColor: 'var(--ms-surface)',
            border: '1px solid var(--ms-border-strong)',
            color: 'var(--ms-text)',
          }}
          value={sortDir}
          onChange={(e) => setSortDir(e.target.value as SortDir)}
          aria-label="Sort direction"
        >
          <option value="desc">Descending</option>
          <option value="asc">Ascending</option>
        </select>
      </div>

      {customersQuery.error && (
        <p className="text-sm mb-3" style={{ color: '#C96A5A' }}>{getApiErrorMessage(customersQuery.error)}</p>
      )}
      {(customersQuery.hasNextPage || search.trim()) && (
        <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>
          {search.trim()
            ? 'Search applies to customers already loaded. Load more to include additional rows in search.'
            : customersQuery.hasNextPage
              ? 'More customers are available — use Load more.'
              : null}
        </p>
      )}

      {isLoading ? <Spinner /> : (
        <Card>
          {filtered.length === 0 ? <EmptyState message="No customers found." /> : (
            <>
            <div className="md:hidden divide-y" style={{ borderColor: 'var(--ms-border)' }}>
              {filtered.map((c: Customer) => (
                <div key={c.id} className="p-4 space-y-2">
                  <Link to={`/customers/${c.id}`} className="font-medium" style={{ color: 'var(--ms-accent)' }}>
                    {c.full_name}
                  </Link>
                  <div className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                    <p>{c.email ?? 'No email'}</p>
                    <p>{c.phone ?? 'No phone'}</p>
                  </div>
                  <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Added {formatDate(c.created_at)}</p>
                </div>
              ))}
            </div>

            <table className="w-full text-sm hidden md:table">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--ms-border)' }}>
                  {['Name', 'Email', 'Phone', 'Added'].map(h => (
                    <th
                      key={h}
                      className="px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase"
                      style={{ color: 'var(--ms-text-muted)' }}
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
                    style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--ms-border)' : 'none' }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td className="px-5 py-3.5">
                      <Link
                        to={`/customers/${c.id}`}
                        className="font-medium hover:underline"
                        style={{ color: 'var(--ms-accent)' }}
                      >
                        {c.full_name}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5" style={{ color: 'var(--ms-text-mid)' }}>{c.email ?? '—'}</td>
                    <td className="px-5 py-3.5" style={{ color: 'var(--ms-text-mid)' }}>{c.phone ?? '—'}</td>
                    <td className="px-5 py-3.5" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </>
          )}
        </Card>
      )}

      {customersQuery.hasNextPage && (
        <div className="mt-6 flex justify-center">
          <Button
            variant="secondary"
            onClick={() => void customersQuery.fetchNextPage()}
            disabled={customersQuery.isFetchingNextPage}
          >
            {customersQuery.isFetchingNextPage ? 'Loading…' : 'Load more customers'}
          </Button>
        </div>
      )}
    </div>
  )
}
