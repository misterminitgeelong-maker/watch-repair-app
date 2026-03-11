import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/context/AuthContext'
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
import StatusPage from '@/pages/StatusPage'
import LandingPage from '@/pages/LandingPage'
import AccountsPage from '@/pages/AccountsPage'
import PlatformAdminUsersPage from '@/pages/PlatformAdminUsersPage'
import ShoeRepairsPage from '@/pages/ShoeRepairsPage'
import ShoeJobDetailPage from '@/pages/ShoeJobDetailPage'

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

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
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            {/* Protected app shell */}
            <Route element={<AppShell />}>
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="customers" element={<CustomersPage />} />
              <Route path="customers/:id" element={<CustomerDetailPage />} />
              <Route path="jobs" element={<JobsPage />} />
              <Route path="jobs/:id" element={<JobDetailPage />} />
              <Route path="quotes" element={<QuotesPage />} />
              <Route path="invoices" element={<InvoicesPage />} />
              <Route path="invoices/:id" element={<InvoiceDetailPage />} />
              <Route path="invoices/:id/print" element={<PrintInvoicePage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="database" element={<DatabasePage />} />
              <Route path="accounts" element={<AccountsPage />} />
              <Route path="platform-admin/users" element={<PlatformAdminUsersPage />} />
              <Route path="shoe-repairs" element={<ShoeRepairsPage />} />
              <Route path="shoe-repairs/:id" element={<ShoeJobDetailPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
