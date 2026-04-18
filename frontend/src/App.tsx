import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/context/AuthContext'
import { useAuth } from '@/context/AuthContext'
import AppShell from '@/components/AppShell'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { Spinner } from '@/components/ui'
import type { FeatureKey } from '@/lib/api'

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const CustomersPage = lazy(() => import('@/pages/CustomersPage'))
const CustomerDetailPage = lazy(() => import('@/pages/CustomerDetailPage'))
const JobsPage = lazy(() => import('@/pages/JobsPage'))
const JobDetailPage = lazy(() => import('@/pages/JobDetailPage'))
const QuotesPage = lazy(() => import('@/pages/QuotesPage'))
const InvoicesPage = lazy(() => import('@/pages/InvoicesPage').then((module) => ({ default: module.InvoicesPage })))
const InvoiceDetailPage = lazy(() => import('@/pages/InvoicesPage').then((module) => ({ default: module.InvoiceDetailPage })))
const ApprovePage = lazy(() => import('@/pages/ApprovePage'))
const PrintInvoicePage = lazy(() => import('@/pages/PrintInvoicePage'))
const DatabasePage = lazy(() => import('@/pages/DatabasePage'))
const CataloguePage = lazy(() => import('@/pages/CataloguePage'))
const ToolkitPage = lazy(() => import('@/pages/ToolkitPage'))
const ReportsPage = lazy(() => import('@/pages/ReportsPage'))
const InboxPage = lazy(() => import('@/pages/InboxPage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const SignupPage = lazy(() => import('@/pages/SignupPage'))
const SignupCheckoutPage = lazy(() => import('@/pages/SignupCheckoutPage'))
const StatusPage = lazy(() => import('@/pages/StatusPage'))
const ShoeStatusPage = lazy(() => import('@/pages/ShoeStatusPage'))
const MobileBookingPage = lazy(() => import('@/pages/MobileBookingPage'))
const MobileInvoicePage = lazy(() => import('@/pages/MobileInvoicePage'))
const MobileJobIntakePage = lazy(() => import('@/pages/MobileJobIntakePage'))
const LandingPage = lazy(() => import('@/pages/LandingPage'))
const PricingPage = lazy(() => import('@/pages/PricingPage'))
const AccountsPage = lazy(() => import('@/pages/AccountsPage'))
const PlatformAdminUsersPage = lazy(() => import('@/pages/PlatformAdminUsersPage'))
const ShoeRepairsPage = lazy(() => import('@/pages/ShoeRepairsPage'))
const ShoeJobDetailPage = lazy(() => import('@/pages/ShoeJobDetailPage'))
const ShoeServicesPage = lazy(() => import('@/pages/ShoeServicesPage'))
const PrintWatchIntakeTicketsPage = lazy(() => import('@/pages/PrintWatchIntakeTicketsPage'))
const PrintShoeIntakeTicketsPage = lazy(() => import('@/pages/PrintShoeIntakeTicketsPage'))
const AutoKeyJobsPage = lazy(() => import('@/pages/AutoKeyJobsPage'))
const AutoKeyJobDetailPage = lazy(() => import('@/pages/AutoKeyJobDetailPage'))
const CustomerAccountsPage = lazy(() => import('@/pages/CustomerAccountsPage'))
const ParentAccountPage = lazy(() => import('@/pages/ParentAccountPage'))
const StocktakesPage = lazy(() => import('@/pages/StocktakesPage'))
const StocktakeWorkspacePage = lazy(() => import('@/pages/StocktakeWorkspacePage'))
const StocktakeSummaryPage = lazy(() => import('@/pages/StocktakeSummaryPage'))
const ProspectsPage = lazy(() => import('@/pages/ProspectsPage'))
const MobileServicesTeamPage = lazy(() => import('@/pages/MobileServicesTeamPage'))
const SubscriptionRequiredPage = lazy(() => import('@/pages/SubscriptionRequiredPage'))
const CustomerPortalPage = lazy(() => import('@/pages/CustomerPortalPage'))
const ShoeApprovePage = lazy(() => import('@/pages/ShoeApprovePage'))

function RouteFallback() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner />
    </div>
  )
}

function FeatureGate({ feature, children }: { feature: FeatureKey; children: React.ReactNode }) {
  const { hasFeature, role } = useAuth()
  if (role === 'platform_admin' || hasFeature(feature)) return <>{children}</>
  return <Navigate to="/dashboard" replace />
}

function AutoKeySection() {
  return <Outlet />
}

function LocationBoundary({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  return <ErrorBoundary key={location.pathname}>{children}</ErrorBoundary>
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AuthProvider>
          <LocationBoundary>
            <Suspense fallback={<RouteFallback />}>
              <Routes>
            {/* Public — no auth required */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/pricing" element={<PricingPage />} />
            <Route path="/approve/:token" element={<ApprovePage />} />
            <Route path="/status/:token" element={<StatusPage />} />
            <Route path="/shoe-status/:token" element={<ShoeStatusPage />} />
            <Route path="/customer-portal" element={<CustomerPortalPage />} />
            <Route path="/customer-portal/s/:token" element={<CustomerPortalPage />} />
            <Route path="/shoe-approve/:token" element={<ShoeApprovePage />} />
            <Route path="/mobile-booking/:token" element={<MobileBookingPage />} />
            <Route path="/mobile-invoice/:token" element={<MobileInvoicePage />} />
            <Route path="/mobile-job-intake/:token" element={<MobileJobIntakePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/signup/checkout" element={<SignupCheckoutPage />} />
            {/* Protected app shell */}
            <Route element={<AppShell />}>
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="customers" element={<CustomersPage />} />
              <Route path="customers/:id" element={<CustomerDetailPage />} />
              <Route path="jobs" element={<FeatureGate feature="watch"><JobsPage /></FeatureGate>} />
              <Route path="jobs/:id" element={<FeatureGate feature="watch"><JobDetailPage /></FeatureGate>} />
              <Route path="jobs/:id/intake-print" element={<FeatureGate feature="watch"><PrintWatchIntakeTicketsPage /></FeatureGate>} />
              <Route path="catalogue" element={<FeatureGate feature="watch"><CataloguePage /></FeatureGate>} />
              <Route path="quotes" element={<QuotesPage />} />
              <Route path="invoices" element={<InvoicesPage />} />
              <Route path="invoices/:id" element={<InvoiceDetailPage />} />
              <Route path="invoices/:id/print" element={<PrintInvoicePage />} />
              <Route path="inbox" element={<InboxPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="stocktakes" element={<StocktakesPage />} />
              <Route path="stocktakes/:id" element={<StocktakeWorkspacePage />} />
              <Route path="stocktakes/:id/summary" element={<StocktakeSummaryPage />} />
              <Route path="database" element={<DatabasePage />} />
              <Route path="subscription-required" element={<SubscriptionRequiredPage />} />
              <Route path="accounts" element={<AccountsPage />} />
              <Route
                path="auto-key"
                element={
                  <FeatureGate feature="auto_key">
                    <AutoKeySection />
                  </FeatureGate>
                }
              >
                <Route index element={<AutoKeyJobsPage />} />
                <Route path="team" element={<MobileServicesTeamPage />} />
                <Route path="prospects" element={<ProspectsPage />} />
                <Route path="toolkit" element={<ToolkitPage />} />
                <Route path=":id" element={<AutoKeyJobDetailPage />} />
              </Route>
              <Route path="prospects" element={<Navigate to="/auto-key/prospects" replace />} />
              <Route path="toolkit" element={<Navigate to="/auto-key/toolkit" replace />} />
              <Route path="team" element={<Navigate to="/auto-key/team" replace />} />
              <Route path="customer-accounts" element={<FeatureGate feature="customer_accounts"><CustomerAccountsPage /></FeatureGate>} />
              <Route path="parent-account" element={<FeatureGate feature="multi_site"><ParentAccountPage /></FeatureGate>} />
              <Route path="platform-admin/users" element={<PlatformAdminUsersPage />} />
              <Route path="shoe-repairs" element={<FeatureGate feature="shoe"><ShoeRepairsPage /></FeatureGate>} />
              <Route path="shoe-repairs/services" element={<FeatureGate feature="shoe"><ShoeServicesPage /></FeatureGate>} />
              <Route path="shoe-repairs/:id" element={<FeatureGate feature="shoe"><ShoeJobDetailPage /></FeatureGate>} />
              <Route path="shoe-repairs/:id/intake-print" element={<FeatureGate feature="shoe"><PrintShoeIntakeTicketsPage /></FeatureGate>} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </LocationBoundary>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
