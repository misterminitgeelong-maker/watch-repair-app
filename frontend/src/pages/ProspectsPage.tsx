import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listProspectCategories, searchProspects, Prospect } from '@/lib/api'
import { Select, Button, Input } from '@/components/ui'

export default function ProspectsPage() {
  const { data: catData } = useQuery(['prospect-categories'], () => listProspectCategories().then(r => r.data))
  const [category, setCategory] = useState<string | null>(null)

  const { data: searchData, refetch, isFetching } = useQuery(
    ['prospects', category],
    () => searchProspects(category || '').then(r => r.data),
    { enabled: false }
  )

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">Prospects</h1>

      <div className="mb-4 flex gap-3">
        <Select
          label="Category"
          value={category ?? ''}
          onChange={(e) => setCategory(e.target.value || null)}
        >
          <option value="">Select category</option>
          {catData?.categories?.map((c: { key: string; label: string }) => (
            <option key={c.key} value={c.key}>{c.label}</option>
          ))}
        </Select>
        <Button onClick={() => refetch()} disabled={!category || isFetching}>Search</Button>
      </div>

      <div>
        {searchData?.results?.length ? (
          <ul className="space-y-3">
            {searchData.results.map((p: Prospect) => (
              <li key={p.place_id} className="p-3 rounded-lg border" style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)' }}>
                <div className="font-semibold">{p.name}</div>
                <div className="text-sm">{p.address}</div>
                <div className="text-sm mt-1">{p.phone} {p.website && (<a href={p.website} className="ml-2 text-cafe-gold">Website</a>)}</div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>No results. Choose a category and click Search.</div>
        )}
      </div>
    </div>
  )
}
