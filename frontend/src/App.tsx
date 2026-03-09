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
            <Route path="/approve/:token" element={<ApprovePage />} />
            {/* Protected app shell */}
            <Route element={<AppShell />}>
              <Route path="login" element={<Navigate to="/" replace />} />
              <Route index element={<DashboardPage />} />
              <Route path="customers" element={<CustomersPage />} />
              <Route path="customers/:id" element={<CustomerDetailPage />} />
              <Route path="jobs" element={<JobsPage />} />
              <Route path="jobs/:id" element={<JobDetailPage />} />
              <Route path="quotes" element={<QuotesPage />} />
              <Route path="invoices" element={<InvoicesPage />} />
              <Route path="invoices/:id" element={<InvoiceDetailPage />} />
              <Route path="invoices/:id/print" element={<PrintInvoicePage />} />
              <Route path="database" element={<DatabasePage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
