import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ChevronLeft, Download } from 'lucide-react'
import { exportStocktake, getStocktakeReport } from '@/lib/api'
import { Button, Card, EmptyState, PageHeader, Spinner } from '@/components/ui'
import { formatCents, formatDate } from '@/lib/utils'

async function downloadReport(id: string, format: 'csv' | 'xlsx') {
  const response = await exportStocktake(id, format)
  const blob = new Blob([response.data], {
    type: format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = `stocktake-${id}.${format}`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(href)
}

export default function StocktakeSummaryPage() {
  const { id } = useParams<{ id: string }>()

  const { data: report, isLoading } = useQuery({
    queryKey: ['stocktake-report', id],
    queryFn: () => getStocktakeReport(id!).then(r => r.data),
    enabled: !!id,
  })

  if (isLoading) return <Spinner />
  if (!report) return <EmptyState message="Stocktake report not found." />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Link
          to={`/stocktakes/${report.session.id}`}
          className="inline-flex items-center gap-1 text-sm font-medium"
          style={{ color: 'var(--cafe-text-muted)' }}
        >
          <ChevronLeft size={14} /> Back to workspace
        </Link>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => downloadReport(report.session.id, 'csv')}>
            <Download size={15} /> CSV
          </Button>
          <Button onClick={() => downloadReport(report.session.id, 'xlsx')}>
            <Download size={15} /> Excel
          </Button>
        </div>
      </div>

      <PageHeader title={`${report.session.name} summary`} />

      <div className="grid grid-cols-2 xl:grid-cols-5 gap-4">
        <Card className="p-4"><div className="text-xs uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Matched</div><div className="mt-2 text-2xl font-semibold">{report.matched_item_count}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Missing</div><div className="mt-2 text-2xl font-semibold">{report.missing_item_count}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Over</div><div className="mt-2 text-2xl font-semibold">{report.over_count_item_count}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Variance qty</div><div className="mt-2 text-2xl font-semibold">{report.total_variance_qty}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Variance value</div><div className="mt-2 text-2xl font-semibold">{formatCents(report.total_variance_value_cents)}</div></Card>
      </div>

      <Card className="p-5">
        <div className="flex flex-wrap gap-4 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
          <div>Status: <strong style={{ color: 'var(--cafe-text)' }}>{report.session.status.replace(/_/g, ' ')}</strong></div>
          <div>Created: <strong style={{ color: 'var(--cafe-text)' }}>{formatDate(report.session.created_at)}</strong></div>
          <div>Completed: <strong style={{ color: 'var(--cafe-text)' }}>{report.session.completed_at ? formatDate(report.session.completed_at) : 'Not completed'}</strong></div>
          <div>Progress: <strong style={{ color: 'var(--cafe-text)' }}>{report.session.progress.counted_items} / {report.session.progress.total_items}</strong></div>
        </div>
      </Card>

      <Card>
        <div className="px-5 py-4" style={{ borderBottom: '1px solid var(--cafe-border)' }}>
          <h2 className="font-semibold" style={{ color: 'var(--cafe-text)' }}>Group summary</h2>
          <p className="text-sm mt-1" style={{ color: 'var(--cafe-text-muted)' }}>Variance totals by group code and category.</p>
        </div>

        <div className="divide-y" style={{ borderColor: 'var(--cafe-border)' }}>
          {report.groups.map(group => (
            <div key={group.group_code} className="px-5 py-4 grid grid-cols-1 md:grid-cols-[1.5fr,0.6fr,0.6fr,0.8fr] gap-4 items-center">
              <div>
                <div className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{group.group_code} / {group.group_name || 'Unassigned'}</div>
                <div className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>{group.counted_count} counted of {group.item_count} items</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Variances</div>
                <div className="mt-1 font-semibold">{group.variance_count}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Variance qty</div>
                <div className="mt-1 font-semibold">{group.total_variance_qty}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Variance value</div>
                <div className="mt-1 font-semibold">{formatCents(group.total_variance_value_cents)}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}