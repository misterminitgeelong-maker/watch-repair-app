import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/context/AuthContext'
import { useAuth } from '@/context/AuthContext'
import AppShell from '@/components/AppShell'
import DashboardPage from '@/pages/DashboardPage'
import CustomersPage from '@/pages/CustomersPage'
import CustomerDetailPage from '@/pages/CustomerDetailPage'
import JobsPage from '@/pages/JobsPage'
import JobDetailPage from '@/pages/JobDetailPage'
import QuotesPage from '@/pages/QuotesPage'
import { InvoicesPage, InvoiceDetailPage } from '@/pages/InvoicesPage'
import ApprovePage from '@/pages/ApprovePage'
import PrintInvoicePage from '@/pages/PrintInvoicePage'
import DatabasePage from '@/pages/DatabasePage'
import ReportsPage from '@/pages/ReportsPage'
import LoginPage from '@/pages/LoginPage'
import SignupPage from '@/pages/SignupPage'
import SignupCheckoutPage from '@/pages/SignupCheckoutPage'
import StatusPage from '@/pages/StatusPage'
import ShoeStatusPage from '@/pages/ShoeStatusPage'
import LandingPage from '@/pages/LandingPage'
import AccountsPage from '@/pages/AccountsPage'
import PlatformAdminUsersPage from '@/pages/PlatformAdminUsersPage'
import ShoeRepairsPage from '@/pages/ShoeRepairsPage'
import ShoeJobDetailPage from '@/pages/ShoeJobDetailPage'
import PrintWatchIntakeTicketsPage from '@/pages/PrintWatchIntakeTicketsPage'
import PrintShoeIntakeTicketsPage from '@/pages/PrintShoeIntakeTicketsPage'
import AutoKeyJobsPage from '@/pages/AutoKeyJobsPage'
import AutoKeyJobDetailPage from '@/pages/AutoKeyJobDetailPage'
import CustomerAccountsPage from '@/pages/CustomerAccountsPage'
import ParentAccountPage from '@/pages/ParentAccountPage'
import StocktakesPage from '@/pages/StocktakesPage'
import StocktakeWorkspacePage from '@/pages/StocktakeWorkspacePage'
import StocktakeSummaryPage from '@/pages/StocktakeSummaryPage'
import type { FeatureKey } from '@/lib/api'

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

function FeatureGate({ feature, children }: { feature: FeatureKey; children: React.ReactNode }) {
  const { hasFeature, role } = useAuth()
  if (role === 'platform_admin' || hasFeature(feature)) return <>{children}</>
  return <Navigate to="/dashboard" replace />
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public — no auth required */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/approve/:token" element={<ApprovePage />} />
            <Route path="/status/:token" element={<StatusPage />} />
            <Route path="/shoe-status/:token" element={<ShoeStatusPage />} />
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
              <Route path="quotes" element={<QuotesPage />} />
              <Route path="invoices" element={<InvoicesPage />} />
              <Route path="invoices/:id" element={<InvoiceDetailPage />} />
              <Route path="invoices/:id/print" element={<PrintInvoicePage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="stocktakes" element={<StocktakesPage />} />
              <Route path="stocktakes/:id" element={<StocktakeWorkspacePage />} />
              <Route path="stocktakes/:id/summary" element={<StocktakeSummaryPage />} />
              <Route path="database" element={<DatabasePage />} />
              <Route path="accounts" element={<AccountsPage />} />
              <Route path="auto-key" element={<FeatureGate feature="auto_key"><AutoKeyJobsPage /></FeatureGate>} />
              <Route path="auto-key/:id" element={<FeatureGate feature="auto_key"><AutoKeyJobDetailPage /></FeatureGate>} />
              <Route path="customer-accounts" element={<FeatureGate feature="customer_accounts"><CustomerAccountsPage /></FeatureGate>} />
              <Route path="parent-account" element={<FeatureGate feature="multi_site"><ParentAccountPage /></FeatureGate>} />
              <Route path="platform-admin/users" element={<PlatformAdminUsersPage />} />
              <Route path="shoe-repairs" element={<FeatureGate feature="shoe"><ShoeRepairsPage /></FeatureGate>} />
              <Route path="shoe-repairs/:id" element={<FeatureGate feature="shoe"><ShoeJobDetailPage /></FeatureGate>} />
              <Route path="shoe-repairs/:id/intake-print" element={<FeatureGate feature="shoe"><PrintShoeIntakeTicketsPage /></FeatureGate>} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
