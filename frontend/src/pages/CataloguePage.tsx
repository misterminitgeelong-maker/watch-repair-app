import { PageHeader } from '@/components/ui'
import WatchCatalogueTab from '@/components/WatchCatalogueTab'

export default function CataloguePage() {
  return (
    <div>
      <PageHeader title="Watch Catalogue" />
      <p className="text-sm mb-6" style={{ color: 'var(--cafe-text-muted)' }}>
        Repair services and movement database. Search by name or caliber.
      </p>
      <div className="max-w-3xl">
        <WatchCatalogueTab />
      </div>
    </div>
  )
}
