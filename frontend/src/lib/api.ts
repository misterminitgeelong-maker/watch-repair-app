import axios from 'axios'

const api = axios.create({ baseURL: '/v1' })

// Attach JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Keep session state in sync on 401 (no forced redirect in test mode)
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.dispatchEvent(new Event('auth:token-cleared'))
    }
    return Promise.reject(err)
  }
)

export default api

// ── Auth ──────────────────────────────────────────────────────────────────────
export interface TokenResponse { access_token: string; token_type: string }
export const login = (tenant_slug: string, email: string, password: string) =>
  api.post<TokenResponse>('/auth/login', { tenant_slug, email, password })

export interface SignupResponse {
  tenant_id: string
  user: {
    id: string
    tenant_id: string
    email: string
    full_name: string
    role: string
    is_active: boolean
  }
  access_token: string
  token_type: string
  expires_in_seconds: number
}
export const signup = (data: {
  tenant_name: string
  tenant_slug: string
  email: string
  full_name: string
  password: string
}) => api.post<SignupResponse>('/auth/signup', data)

export const bootstrap = (data: { tenant_name: string; tenant_slug: string; owner_email: string; owner_password: string; owner_full_name?: string }) =>
  api.post('/auth/bootstrap', data)

// ── Customers ─────────────────────────────────────────────────────────────────
export interface Customer {
  id: string; tenant_id: string; full_name: string
  email?: string; phone?: string; address?: string; notes?: string; created_at: string
}
export const listCustomers = () => api.get<Customer[]>('/customers')
export const getCustomer = (id: string) => api.get<Customer>(`/customers/${id}`)
export const createCustomer = (data: Omit<Customer, 'id' | 'tenant_id' | 'created_at'>) =>
  api.post<Customer>('/customers', data)
export const updateCustomer = (id: string, data: Partial<Omit<Customer, 'id' | 'tenant_id' | 'created_at'>>) =>
  api.patch<Customer>(`/customers/${id}`, data)

// ── Watches ───────────────────────────────────────────────────────────────────
export interface Watch {
  id: string; tenant_id: string; customer_id: string
  brand?: string; model?: string; serial_number?: string
  movement_type?: string; condition_notes?: string; created_at: string
}
export const listWatches = (customerId?: string) =>
  api.get<Watch[]>('/watches', { params: customerId ? { customer_id: customerId } : {} })
export const createWatch = (data: Omit<Watch, 'id' | 'tenant_id' | 'created_at'>) =>
  api.post<Watch>('/watches', data)

// ── Repair Jobs ───────────────────────────────────────────────────────────────
export type JobStatus = 'awaiting_quote' | 'awaiting_go_ahead' | 'go_ahead' | 'no_go' | 'working_on' | 'awaiting_parts' | 'parts_to_order' | 'sent_to_labanda' | 'quoted_by_labanda' | 'service' | 'completed' | 'awaiting_collection' | 'collected'
export interface RepairJob {
  id: string; tenant_id: string; watch_id: string; assigned_user_id?: string
  job_number: string; status_token: string; title: string; description?: string; priority: string
  status: JobStatus; salesperson?: string; collection_date?: string; deposit_cents: number; pre_quote_cents: number; cost_cents: number; created_at: string
}
export const listJobs = () => api.get<RepairJob[]>('/repair-jobs')
export const getJob = (id: string) => api.get<RepairJob>(`/repair-jobs/${id}`)
export interface RepairJobCreatePayload {
  watch_id: string
  assigned_user_id?: string
  title: string
  description?: string
  priority: string
  status: JobStatus
  salesperson?: string
  collection_date?: string
  deposit_cents: number
  pre_quote_cents: number
  cost_cents: number
}
export const createJob = (data: RepairJobCreatePayload) =>
  api.post<RepairJob>('/repair-jobs', data)
export const updateJob = (id: string, data: {
  cost_cents?: number
  pre_quote_cents?: number
  priority?: string
  salesperson?: string
  collection_date?: string
  deposit_cents?: number
  description?: string
}) => api.patch<RepairJob>(`/repair-jobs/${id}`, data)
export const updateJobStatus = (id: string, status: JobStatus, note?: string) =>
  api.post(`/repair-jobs/${id}/status`, { status, note })

export const quickStatusAction = (id: string, status: JobStatus, note?: string) =>
  api.post<RepairJob>(`/repair-jobs/${id}/quick-status`, { status, note })

export interface IntakePayload {
  intake_notes?: string
  pre_quote_cents: number
  has_scratches: boolean
  has_dents: boolean
  has_cracked_crystal: boolean
  crown_missing: boolean
  strap_damage: boolean
}
export const submitJobIntake = (id: string, payload: IntakePayload) =>
  api.post<RepairJob>(`/repair-jobs/${id}/intake`, payload)

// ── Quotes ────────────────────────────────────────────────────────────────────
export type QuoteStatus = 'draft' | 'sent' | 'approved' | 'declined' | 'expired'
export interface QuoteLineItemInput {
  item_type: 'labor' | 'part' | 'fee'; description: string
  quantity: number; unit_price_cents: number
}
export interface Quote {
  id: string; tenant_id: string; repair_job_id: string; status: QuoteStatus
  subtotal_cents: number; tax_cents: number; total_cents: number; currency: string
  approval_token: string; sent_at?: string; created_at: string
}
export const listQuotes = (repairJobId?: string) =>
  api.get<Quote[]>('/quotes', repairJobId ? { params: { repair_job_id: repairJobId } } : undefined)
export const createQuote = (data: { repair_job_id: string; tax_cents: number; line_items: QuoteLineItemInput[] }) =>
  api.post<Quote>('/quotes', data)
export const sendQuote = (id: string) => api.post<{ id: string; status: string; sent_at: string; approval_token: string }>(`/quotes/${id}/send`)
export const getQuoteLineItems = (quoteId: string) => api.get<Array<QuoteLineItemInput & { id: string; total_price_cents: number }>>(`/quotes/${quoteId}/line-items`)

// Public (no auth)
export const getPublicQuote = (token: string) =>
  axios.get<{ id: string; status: string; subtotal_cents: number; tax_cents: number; total_cents: number; currency: string; sent_at?: string; line_items: Array<{ item_type: string; description: string; quantity: number; unit_price_cents: number; total_price_cents: number }> }>(`/v1/public/quotes/${token}`)
export const submitQuoteDecision = (token: string, decision: 'approved' | 'declined') =>
  axios.post(`/v1/public/quotes/${token}/decision`, { decision })

export interface PublicJobStatus {
  job_number: string
  status: string
  title: string
  description?: string
  priority: string
  pre_quote_cents: number
  created_at: string
  watch: {
    brand?: string
    model?: string
    serial_number?: string
  }
  history: Array<{
    old_status?: string
    new_status: string
    change_note?: string
    created_at: string
  }>
}
export const getPublicJobStatus = (token: string) =>
  axios.get<PublicJobStatus>(`/v1/public/jobs/${token}`)

export const getPublicJobQrUrl = (token: string) =>
  `/v1/public/jobs/${token}/qr`

// ── Work Logs ─────────────────────────────────────────────────────────────────
export interface WorkLog {
  id: string; tenant_id: string; repair_job_id: string; user_id?: string
  note?: string; minutes_spent: number; started_at?: string; ended_at?: string; created_at: string
}
export const listWorkLogs = (repairJobId: string) =>
  api.get<WorkLog[]>('/work-logs', { params: { repair_job_id: repairJobId } })
export const createWorkLog = (data: { repair_job_id: string; note?: string; minutes_spent?: number }) =>
  api.post<WorkLog>('/work-logs', data)

// ── Attachments ───────────────────────────────────────────────────────────────
export interface Attachment {
  id: string; tenant_id: string; repair_job_id?: string; watch_id?: string
  storage_key: string; file_name?: string; content_type?: string; file_size_bytes?: number
  label?: string; created_at: string
}
export const listAttachments = (repairJobId: string) =>
  api.get<Attachment[]>('/attachments', { params: { repair_job_id: repairJobId } })
export const uploadAttachment = (file: File, repairJobId: string, label?: string) => {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams({ repair_job_id: repairJobId })
  if (label) params.append('label', label)
  return api.post<Attachment>(`/attachments?${params.toString()}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
export const getAttachmentDownloadUrl = (storageKey: string) =>
  `/v1/attachments/download/${encodeURIComponent(storageKey)}${localStorage.getItem('token') ? `?access_token=${encodeURIComponent(localStorage.getItem('token') as string)}` : ''}`

// ── Status History ────────────────────────────────────────────────────────────
export interface StatusHistoryEntry {
  id: string; repair_job_id: string; old_status?: string; new_status: string
  changed_by_user_id?: string; change_note?: string; created_at: string
}
export const getStatusHistory = (jobId: string) =>
  api.get<StatusHistoryEntry[]>(`/repair-jobs/${jobId}/status-history`)

// ── Invoices ──────────────────────────────────────────────────────────────────
export interface Invoice {
  id: string; tenant_id: string; repair_job_id: string; quote_id?: string
  invoice_number: string; status: string; subtotal_cents: number
  tax_cents: number; total_cents: number; currency: string; created_at: string
}
export const listInvoices = () => api.get<Invoice[]>('/invoices')
export const getInvoice = (id: string) => api.get<Invoice>(`/invoices/${id}`)
export const recordPayment = (invoiceId: string, amount_cents: number) =>
  api.post(`/invoices/${invoiceId}/payments`, { amount_cents })

// ── CSV Import ────────────────────────────────────────────────────────────────
export interface CsvImportResult {
  import_id: string
  imported: number; skipped: number; customers_created: number; total_rows: number
  skipped_reasons: Record<string, number>
}
export const importCsv = (file: File, options?: { replaceExisting?: boolean }) => {
  const form = new FormData()
  form.append('file', file)
  const params = options?.replaceExisting ? '?replace_existing=true' : ''
  return api.post<CsvImportResult>(`/import/csv${params}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ── Reports ───────────────────────────────────────────────────────────────────
export interface ReportsSummary {
  counts: {
    jobs: number; customers: number; watches: number; quotes: number; invoices: number
  }
  jobs_by_status: Record<string, number>
  quotes_by_status: Record<string, number>
  sales_funnel: {
    approved_quotes: number; sent_quotes: number; declined_quotes: number; approval_rate_percent: number
  }
  financials: {
    billed_cents: number
    revenue_cents: number
    cost_cents: number
    outstanding_cents: number
    gross_profit_cents: number
    gross_margin_percent: number
  }
  operations: {
    work_minutes: number
    avg_revenue_per_job_cents: number
  }
}
export const getReportsSummary = () => api.get<ReportsSummary>('/reports/summary')

// ── Users (admin management) ────────────────────────────────────────────────
export interface TenantUser {
  id: string
  tenant_id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
}

export const listUsers = () => api.get<TenantUser[]>('/users')

export const createUser = (data: {
  email: string
  full_name: string
  password: string
  role?: 'owner' | 'manager' | 'tech' | 'intake'
}) => api.post<TenantUser>('/users', data)

export const updateUser = (
  userId: string,
  data: {
    full_name?: string
    role?: 'owner' | 'manager' | 'tech' | 'intake'
    password?: string
    is_active?: boolean
  },
) => api.patch<TenantUser>(`/users/${userId}`, data)

export interface PlatformUser extends TenantUser {
  tenant_slug: string
  tenant_name: string
}

export const listPlatformUsers = () => api.get<PlatformUser[]>('/platform-admin/users')

// ── Shoe Catalogue ────────────────────────────────────────────────────────────
export interface ShoeCatalogueGroup {
  id: string
  label: string
}

export type ShoePricingType =
  | 'fixed' | 'from' | 'each' | 'pair' | 'pair_from' | 'each_from'
  | 'per_cm' | 'from_per_boot' | 'from_per_strap' | 'per_elastic'
  | 'single' | 'quoted_upon_inspection'

export interface ShoeCatalogueItem {
  key: string
  name: string
  price: number | null
  price_cents: number | null
  pricing_type: ShoePricingType
  group_id: string
  group_label: string
  notes?: string
  includes?: string[]
}

export interface ShoeCombo {
  id: string
  name: string
  discount?: string
  discounts?: string[]
  rule: string
}

export const listShoeCatalogueGroups = () =>
  api.get<ShoeCatalogueGroup[]>('/shoe-catalogue/groups')

export const searchShoeCatalogueItems = (params?: { q?: string; group?: string }) =>
  api.get<ShoeCatalogueItem[]>('/shoe-catalogue/items', { params })

export const listShoeCombos = () =>
  api.get<ShoeCombo[]>('/shoe-catalogue/combos')

export const getShoeGuarantee = () =>
  api.get<{ shoe_repairs: string }>('/shoe-catalogue/guarantee')

// ── Shoes (items being repaired) ──────────────────────────────────────────────
export interface Shoe {
  id: string
  tenant_id: string
  customer_id: string
  shoe_type?: string
  brand?: string
  color?: string
  description_notes?: string
  created_at: string
}

export const listShoes = (customerId?: string) =>
  api.get<Shoe[]>('/shoe-repair-jobs/shoes', customerId ? { params: { customer_id: customerId } } : undefined)

export const createShoe = (data: Omit<Shoe, 'id' | 'tenant_id' | 'created_at'>) =>
  api.post<Shoe>('/shoe-repair-jobs/shoes', data)

// ── Shoe Repair Jobs ──────────────────────────────────────────────────────────
export interface ShoeRepairJobItem {
  id: string
  shoe_repair_job_id: string
  catalogue_key: string
  catalogue_group: string
  item_name: string
  pricing_type: ShoePricingType
  unit_price_cents: number | null
  quantity: number
  notes?: string
  created_at: string
}

export interface ShoeRepairJob {
  id: string
  tenant_id: string
  shoe_id: string
  assigned_user_id?: string
  job_number: string
  status_token: string
  title: string
  description?: string
  priority: string
  status: string
  salesperson?: string
  collection_date?: string
  deposit_cents: number
  cost_cents: number
  created_at: string
  items: ShoeRepairJobItem[]
}

export interface ShoeRepairJobCreatePayload {
  shoe_id: string
  title: string
  description?: string
  priority?: string
  status?: string
  salesperson?: string
  collection_date?: string
  deposit_cents?: number
  cost_cents?: number
  items: Array<{
    catalogue_key: string
    catalogue_group: string
    item_name: string
    pricing_type: ShoePricingType
    unit_price_cents: number | null
    quantity?: number
    notes?: string
  }>
}

export const listShoeRepairJobs = (status?: string) =>
  api.get<ShoeRepairJob[]>('/shoe-repair-jobs', status ? { params: { status } } : undefined)

export const getShoeRepairJob = (id: string) =>
  api.get<ShoeRepairJob>(`/shoe-repair-jobs/${id}`)

export const createShoeRepairJob = (data: ShoeRepairJobCreatePayload) =>
  api.post<ShoeRepairJob>('/shoe-repair-jobs', data)

export const updateShoeRepairJob = (id: string, data: Partial<{
  title: string; description: string; priority: string
  salesperson: string; collection_date: string
  deposit_cents: number; cost_cents: number
}>) => api.patch<ShoeRepairJob>(`/shoe-repair-jobs/${id}`, data)

export const updateShoeRepairJobStatus = (id: string, status: string, note?: string) =>
  api.post<ShoeRepairJob>(`/shoe-repair-jobs/${id}/status`, { status, note })

// Pricing type display helper (used by both modal and page)
export function formatShoePricingType(type: ShoePricingType, priceCents: number | null): string {
  if (type === 'quoted_upon_inspection') return 'Quoted upon inspection'
  if (priceCents == null) return 'Price on enquiry'
  const dollars = (priceCents / 100).toFixed(2)
  switch (type) {
    case 'fixed':        return `$${dollars}`
    case 'from':         return `From $${dollars}`
    case 'each':         return `$${dollars} each`
    case 'pair':         return `$${dollars} / pair`
    case 'pair_from':    return `From $${dollars} / pair`
    case 'each_from':    return `From $${dollars} each`
    case 'per_cm':       return `$${dollars} per cm`
    case 'from_per_boot':   return `From $${dollars} / boot`
    case 'from_per_strap':  return `From $${dollars} / strap`
    case 'per_elastic':     return `$${dollars} per elastic`
    case 'single':          return `$${dollars} (single)`
    default:             return `$${dollars}`
  }
}
