import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/ui'
import WatchCatalogueTab from '@/components/WatchCatalogueTab'

export default function CataloguePage() {
  return (
    <div>
      <PageHeader title="Watch Repairs" />
      <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
        Movement services, batteries, pressure testing, and full servicing.
      </p>

      <div className="mb-6 flex items-center gap-2">
        <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
          <Link
            to="/jobs"
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
            style={{
              backgroundColor: 'transparent',
              color: 'var(--ms-text-muted)',
              textDecoration: 'none',
            }}
          >
            Jobs
          </Link>
          <span
            className="px-3 py-1.5 text-xs font-semibold rounded-md"
            style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)' }}
          >
            Catalogue
          </span>
        </div>
      </div>

      <p className="text-sm mb-6" style={{ color: 'var(--ms-text-muted)' }}>
        Repair services and movement database. Search by name or caliber.
      </p>
      <div className="max-w-3xl">
        <WatchCatalogueTab />
      </div>
    </div>
  )
}
