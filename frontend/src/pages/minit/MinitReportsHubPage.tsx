import { Link } from 'react-router-dom'
import { BarChart3, KeyRound, Wrench } from 'lucide-react'
import { Card, PageHeader } from '@/components/ui'

function ReportLink({
  to,
  icon: Icon,
  title,
  description,
}: {
  to: string
  icon: typeof BarChart3
  title: string
  description: string
}) {
  return (
    <Link to={to} className="block hover:opacity-95 transition-opacity">
      <Card className="p-5 h-full">
        <div className="flex items-start gap-4">
          <div
            className="shrink-0 w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: 'rgba(79,130,201,0.12)', color: 'var(--ms-accent)' }}
          >
            <Icon size={20} />
          </div>
          <div>
            <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
              {title}
            </p>
            <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
              {description}
            </p>
          </div>
        </div>
      </Card>
    </Link>
  )
}

export default function MinitReportsHubPage() {
  return (
    <div>
      <PageHeader title="Reports" />
      <p className="text-sm mb-6" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Cross-shop reporting and network diagnostics.
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <ReportLink
          to="/minit/reports/shops"
          icon={BarChart3}
          title="Shop reports"
          description="Booking requests, accept/decline rates, and quiet shops across the retail network."
        />
        <ReportLink
          to="/minit/mobile-services"
          icon={KeyRound}
          title="Mobile job reports"
          description="Mobile service jobs by operator — referred bookings and shop-initiated jobs."
        />
        <ReportLink
          to="/minit/troubleshooting"
          icon={Wrench}
          title="Troubleshooting"
          description="Failed bookings, stale pending requests, missing operator SMS, and other actionable issues."
        />
      </div>
    </div>
  )
}
