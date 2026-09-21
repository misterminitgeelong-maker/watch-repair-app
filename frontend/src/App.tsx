import { Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/context/AuthContext'
import { useAuth } from '@/context/AuthContext'
import { ThemeProvider } from '@/context/ThemeContext'
import { ToastProvider } from '@/lib/toast'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { FeatureGate, RouteFallback } from '@/components/FeatureGate'
import { defaultHomePathForMinit, isMinitHqUi } from '@/lib/minitProduct'
import { lazyPage } from '@/lib/routePrefetch'

function DashboardRoute() {
  const { product, planCode, tenantSlug, minitHqUi } = useAuth()
  const hq = minitHqUi === true || isMinitHqUi(product, planCode, tenantSlug)
  if (hq) return <Navigate to="/minit/dashboard" replace />
  return (
    <Suspense fallback={<RouteFallback />}>
      <DashboardPage />
    </Suspense>
  )
}

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

const DashboardPage = lazyPage(() => import('@/pages/DashboardPage'))
const AppShell = lazyPage(() => import('@/components/AppShell'))
const ConnectivityBanner = lazyPage(() => import('@/components/ConnectivityBanner'))
const CustomersPage = lazyPage(() => import('@/pages/CustomersPage'))
const CustomerDetailPage = lazyPage(() => import('@/pages/CustomerDetailPage'))
const JobsPage = lazyPage(() => import('@/pages/JobsPage'))
const JobDetailPage = lazyPage(() => import('@/pages/JobDetailPage'))
const QuotesPage = lazyPage(() => import('@/pages/QuotesPage'))
const InvoicesPage = lazyPage(() => import('@/pages/InvoicesPage').then((module) => ({ default: module.InvoicesPage })))
const InvoiceDetailPage = lazyPage(() => import('@/pages/InvoicesPage').then((module) => ({ default: module.InvoiceDetailPage })))
const ApprovePage = lazyPage(() => import('@/pages/ApprovePage'))
const PrintInvoicePage = lazyPage(() => import('@/pages/PrintInvoicePage'))
const DatabasePage = lazyPage(() => import('@/pages/DatabasePage'))
const CataloguePage = lazyPage(() => import('@/pages/CataloguePage'))
const ToolkitPage = lazyPage(() => import('@/pages/ToolkitPage'))
const ReportsPage = lazyPage(() => import('@/pages/ReportsPage'))
const InboxPage = lazyPage(() => import('@/pages/InboxPage'))
const LoginPage = lazyPage(() => import('@/pages/LoginPage'))
const SignupPage = lazyPage(() => import('@/pages/SignupPage'))
const SignupCheckoutPage = lazyPage(() => import('@/pages/SignupCheckoutPage'))
const StatusPage = lazyPage(() => import('@/pages/StatusPage'))
const ShoeStatusPage = lazyPage(() => import('@/pages/ShoeStatusPage'))
const MobileBookingPage = lazyPage(() => import('@/pages/MobileBookingPage'))
const MobileInvoicePage = lazyPage(() => import('@/pages/MobileInvoicePage'))
const MobileQuotePage = lazyPage(() => import('@/pages/MobileQuotePage'))
const MobileJobIntakePage = lazyPage(() => import('@/pages/MobileJobIntakePage'))
const LandingPage = lazyPage(() => import('@/pages/LandingPage'))
const PricingPage = lazyPage(() => import('@/pages/PricingPage'))
const AccountsPage = lazyPage(() => import('@/pages/AccountsPage'))
const PlatformAdminUsersPage = lazyPage(() => import('@/pages/PlatformAdminUsersPage'))
const ShoeRepairsPage = lazyPage(() => import('@/pages/ShoeRepairsPage'))
const ShoeJobDetailPage = lazyPage(() => import('@/pages/ShoeJobDetailPage'))
const ShoeServicesPage = lazyPage(() => import('@/pages/ShoeServicesPage'))
const PrintWatchIntakeTicketsPage = lazyPage(() => import('@/pages/PrintWatchIntakeTicketsPage'))
const PrintShoeIntakeTicketsPage = lazyPage(() => import('@/pages/PrintShoeIntakeTicketsPage'))
const AutoKeyJobsPage = lazyPage(() => import('@/pages/AutoKeyJobsPage'))
const RevenueControlPage = lazyPage(() => import('@/pages/RevenueControlPage'))
const AutoKeyJobDetailPage = lazyPage(() => import('@/pages/AutoKeyJobDetailPage'))
const CustomerAccountsPage = lazyPage(() => import('@/pages/CustomerAccountsPage'))
const ParentAccountPage = lazyPage(() => import('@/pages/ParentAccountPage'))
const StocktakesPage = lazyPage(() => import('@/pages/StocktakesPage'))
const StocktakeWorkspacePage = lazyPage(() => import('@/pages/StocktakeWorkspacePage'))
const StocktakeSummaryPage = lazyPage(() => import('@/pages/StocktakeSummaryPage'))
const ProspectsPage = lazyPage(() => import('@/pages/ProspectsPage'))
const ProspectBoardPage = lazyPage(() => import('@/pages/ProspectBoardPage'))
const LeadInboxPage = lazyPage(() => import('@/pages/LeadInboxPage'))
const MobileServicesTeamPage = lazyPage(() => import('@/pages/MobileServicesTeamPage'))
const SubscriptionRequiredPage = lazyPage(() => import('@/pages/SubscriptionRequiredPage'))
const CustomerPortalPage = lazyPage(() => import('@/pages/CustomerPortalPage'))
const CustomerPortalJobDetailPage = lazyPage(() => import('@/pages/CustomerPortalJobDetailPage'))
const PublicCustomerPortalPage = lazyPage(() => import('@/pages/PublicCustomerPortalPage'))
const ShoeApprovePage = lazyPage(() => import('@/pages/ShoeApprovePage'))
const JobPoolPage = lazyPage(() => import('@/pages/JobPoolPage'))
const PublicIntakePage = lazyPage(() => import('@/pages/PublicIntakePage'))
const CustomerOrdersPage = lazyPage(() => import('@/pages/CustomerOrdersPage'))
const ShopMobileBookingsPage = lazyPage(() => import('@/pages/ShopMobileBookingsPage'))
const ShopOwnerInvitePage = lazyPage(() => import('@/pages/ShopOwnerInvitePage'))
const MinitOperationsPage = lazyPage(() => import('@/pages/minit/MinitOperationsPage'))
const MinitShopsPage = lazyPage(() => import('@/pages/minit/MinitShopsPage'))
const MinitShopReportsPage = lazyPage(() => import('@/pages/minit/MinitShopReportsPage'))
const MinitMobileReportsPage = lazyPage(() => import('@/pages/minit/MinitMobileReportsPage'))
const MinitTroubleshootingPage = lazyPage(() => import('@/pages/minit/MinitTroubleshootingPage'))
const MinitInboxPage = lazyPage(() => import('@/pages/minit/MinitInboxPage'))
const MinitLeadRoutingPage = lazyPage(() => import('@/pages/minit/MinitLeadRoutingPage'))
const MinitAccountsPage = lazyPage(() => import('@/pages/minit/MinitAccountsPage'))
const MinitReportsHubPage = lazyPage(() => import('@/pages/minit/MinitReportsHubPage'))
const MinitRegionCockpitPage = lazyPage(() => import('@/pages/minit/MinitRegionCockpitPage'))

/** Minit HQ pages — allow when server/session says HQ, not only when multi_site is in enabled_features. */
function MinitHqGate({ children }: { children: React.ReactNode }) {
  const { product, planCode, tenantSlug, minitHqUi, hasFeature } = useAuth()
  const { pathname } = useLocation()
  const hq =
    minitHqUi === true ||
    isMinitHqUi(product, planCode, tenantSlug) ||
    hasFeature('multi_site')
  if (hq) return <>{children}</>
  const fallback = defaultHomePathForMinit(planCode, tenantSlug)
  if (pathname === fallback) {
    return (
      <div className="p-6 text-sm" style={{ color: 'var(--ms-error)' }}>
        Minit HQ pages are only available on the support account (mmsupport). Switch back to HQ in the site menu.
      </div>
    )
  }
  return <Navigate to={fallback} replace />
}

function RequireRole({ role, children }: { role: string; children: React.ReactNode }) {
  const { role: actual, authStatus } = useAuth()
  const { pathname } = useLocation()
  if (authStatus === 'authenticating') return <RouteFallback />
  if (actual === role) return <>{children}</>
  if (pathname === '/dashboard') {
    return (
      <div className="p-6 text-sm" style={{ color: 'var(--ms-error)' }}>
        This page is only available to platform admins.
      </div>
    )
  }
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
  const inner = (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <ThemeProvider>
        <ToastProvider>
        <AuthProvider>
          <Suspense fallback={null}><ConnectivityBanner /></Suspense>
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
            <Route path="/customer-portal/job/:jobType/:statusToken" element={<CustomerPortalJobDetailPage />} />
            <Route path="/portal/:slug" element={<PublicCustomerPortalPage />} />
            <Route path="/shoe-approve/:token" element={<ShoeApprovePage />} />
            <Route path="/mobile-booking/:token" element={<MobileBookingPage />} />
            <Route path="/mobile-invoice/:token" element={<MobileInvoicePage />} />
            <Route path="/mobile-quote/:token" element={<MobileQuotePage />} />
            <Route path="/mobile-job-intake/:token" element={<MobileJobIntakePage />} />
            <Route path="/shop-invite/:token" element={<ShopOwnerInvitePage />} />
            <Route path="/intake" element={<PublicIntakePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/signup/checkout" element={<SignupCheckoutPage />} />
            {/* Protected app shell */}
            <Route element={<AppShell />}>
              <Route path="dashboard" element={<DashboardRoute />} />
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
                <Route path="revenue" element={<RevenueControlPage />} />
                <Route path="pool" element={<JobPoolPage />} />
                <Route path="team" element={<MobileServicesTeamPage />} />
                <Route path="prospects" element={<ProspectsPage />} />
                <Route path="prospects/board" element={<ProspectBoardPage />} />
                <Route path="prospects/inbox" element={<LeadInboxPage />} />
                <Route path="toolkit" element={<ToolkitPage />} />
                <Route path=":id" element={<AutoKeyJobDetailPage />} />
              </Route>
              <Route path="prospects" element={<Navigate to="/auto-key/prospects" replace />} />
              <Route path="toolkit" element={<Navigate to="/auto-key/toolkit" replace />} />
              <Route path="team" element={<Navigate to="/auto-key/team" replace />} />
              <Route path="customer-orders" element={<CustomerOrdersPage />} />
              <Route path="customer-accounts" element={<FeatureGate feature="customer_accounts"><CustomerAccountsPage /></FeatureGate>} />
              <Route path="parent-account" element={<FeatureGate feature="multi_site"><ParentAccountPage /></FeatureGate>} />
              <Route path="minit/dashboard" element={<MinitHqGate><MinitOperationsPage /></MinitHqGate>} />
              <Route path="minit/operations" element={<Navigate to="/minit/dashboard" replace />} />
              <Route path="minit/inbox" element={<MinitHqGate><MinitInboxPage /></MinitHqGate>} />
              <Route path="minit/shops" element={<MinitHqGate><MinitShopsPage /></MinitHqGate>} />
              <Route path="minit/lead-routing" element={<MinitHqGate><MinitLeadRoutingPage /></MinitHqGate>} />
              <Route path="minit/mobile-services" element={<MinitHqGate><MinitMobileReportsPage /></MinitHqGate>} />
              <Route path="minit/accounts" element={<MinitHqGate><MinitAccountsPage /></MinitHqGate>} />
              <Route path="minit/reports" element={<MinitHqGate><MinitReportsHubPage /></MinitHqGate>} />
              <Route path="minit/regions/:regionId" element={<MinitHqGate><MinitRegionCockpitPage /></MinitHqGate>} />
              <Route path="minit/reports/shops" element={<MinitHqGate><MinitShopReportsPage /></MinitHqGate>} />
              <Route path="minit/reports/mobile" element={<Navigate to="/minit/mobile-services" replace />} />
              <Route path="minit/troubleshooting" element={<MinitHqGate><MinitTroubleshootingPage /></MinitHqGate>} />
              <Route path="shop-mobile-bookings" element={<FeatureGate feature="shop_mobile_booking"><ShopMobileBookingsPage /></FeatureGate>} />
              <Route path="platform-admin/users" element={<RequireRole role="platform_admin"><PlatformAdminUsersPage /></RequireRole>} />
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
        </ToastProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
  return inner
}
