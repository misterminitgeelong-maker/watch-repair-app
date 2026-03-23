import axios from 'axios'

const api = axios.create({ baseURL: '/v1' })

// Attach JWT on every request
api.interceptors.request.use((config) => {
  const token = getStoredAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401: try refresh once, retry request; otherwise clear tokens
let refreshPromise: Promise<string | null> | null = null
function doRefresh(): Promise<string | null> {
  if (refreshPromise) return refreshPromise
  const rt = getStoredRefreshToken()
  if (!rt) {
    clearStoredTokens()
    window.dispatchEvent(new Event('auth:token-cleared'))
    return Promise.resolve(null)
  }
  refreshPromise = refreshAuth(rt)
    .then((res) => {
      const access = res.data.access_token
      const refresh = res.data.refresh_token ?? null
      setStoredTokens(access, refresh)
      return access
    })
    .catch(() => {
      clearStoredTokens()
      window.dispatchEvent(new Event('auth:token-cleared'))
      return null
    })
    .finally(() => {
      refreshPromise = null
    })
  return refreshPromise
}

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const status = err.response?.status
    const config = err.config
    if (status === 401 && config && !config._retried) {
      config._retried = true
      const newToken = await doRefresh()
      if (newToken) {
        config.headers.Authorization = `Bearer ${newToken}`
        return api.request(config)
      }
    } else if (status === 401) {
      clearStoredTokens()
      window.dispatchEvent(new Event('auth:token-cleared'))
    }
    return Promise.reject(err)
  }
)

export default api

export function getApiErrorMessage(error: unknown, fallback = 'Request failed.'): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const first = detail[0]
      if (typeof first === 'string' && first.trim()) return first
      if (first && typeof first === 'object' && typeof first.msg === 'string' && first.msg.trim()) {
        return first.msg
      }
    }
    if (error.response?.status === 401) return 'Session expired. Please sign in again.'
    if (error.response?.status === 402) return typeof detail === 'string' && detail.trim() ? detail : 'Plan limit reached. Upgrade for more capacity.'
  }
  if (error instanceof Error && error.message?.trim()) return error.message
  return fallback
}

/** True if the error is a 402 plan limit (show upgrade CTA). */
export function isPlanLimitError(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 402
}

// ── Auth ──────────────────────────────────────────────────────────────────────
const REFRESH_TOKEN_KEY = 'refresh_token'
const REMEMBER_ME_KEY = 'remember_me'

export function getRememberMe(): boolean {
  try {
    return localStorage.getItem(REMEMBER_ME_KEY) === 'true'
  } catch {
    // Ignore storage errors, default to true
    return true
  }
}

export function setRememberMe(value: boolean) {
  try {
    if (value) localStorage.setItem(REMEMBER_ME_KEY, 'true')
    else localStorage.removeItem(REMEMBER_ME_KEY)
  } catch {
    // Ignore storage errors
  }
}

function getTokenStorage(): Storage {
  return getRememberMe() ? localStorage : sessionStorage
}

export function getStoredAccessToken(): string | null {
  return getTokenStorage().getItem('token') ?? localStorage.getItem('token') ?? sessionStorage.getItem('token')
}

export function getStoredRefreshToken(): string | null {
  return getTokenStorage().getItem(REFRESH_TOKEN_KEY) ?? localStorage.getItem(REFRESH_TOKEN_KEY) ?? sessionStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setStoredTokens(accessToken: string, refreshToken: string | null) {
  const storage = getTokenStorage()
  storage.setItem('token', accessToken)
  if (refreshToken != null) storage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  else storage.removeItem(REFRESH_TOKEN_KEY)
  if (storage === localStorage) {
    sessionStorage.removeItem('token')
    sessionStorage.removeItem(REFRESH_TOKEN_KEY)
  } else {
    localStorage.removeItem('token')
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  }
}

export function clearStoredTokens() {
  localStorage.removeItem('token')
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  sessionStorage.removeItem('token')
  sessionStorage.removeItem(REFRESH_TOKEN_KEY)
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in_seconds?: number
  refresh_token?: string
  refresh_expires_in_seconds?: number
}
const LOGIN_TIMEOUT_MS = 15_000
export const login = (tenant_slug: string, email: string, password: string) =>
  api.post<TokenResponse>('/auth/login', { tenant_slug, email, password }, { timeout: LOGIN_TIMEOUT_MS })
export const refreshAuth = (refresh_token: string) =>
  api.post<TokenResponse>('/auth/refresh', { refresh_token })
export interface MultiSiteLoginResponse {
  access_token: string
  token_type: string
  expires_in_seconds: number
  refresh_token?: string
  refresh_expires_in_seconds?: number
  active_site_tenant_id: string
  available_sites: SiteOption[]
}
export const multiSiteLogin = (email: string, password: string) =>
  api.post<MultiSiteLoginResponse>('/auth/multi-site-login', { email, password })

export const seedDemoData = () => api.post<{ ok: boolean; created: Record<string, number> }>('/auth/demo-seed', {})

export type PlanCode =
  | 'basic_watch'
  | 'basic_shoe'
  | 'basic_auto_key'
  | 'basic_watch_shoe'
  | 'basic_watch_auto_key'
  | 'basic_shoe_auto_key'
  | 'basic_all_tabs'
  | 'pro'
export type FeatureKey = 'watch' | 'shoe' | 'auto_key' | 'customer_accounts' | 'multi_site' | 'rego_lookup'

export interface SiteOption {
  tenant_id: string
  tenant_slug: string
  tenant_name: string
  user_id: string
  role: string
}

export interface AuthSession {
  user: {
    id: string
    tenant_id: string
    email: string
    full_name: string
    role: string
    is_active: boolean
  }
  tenant_id: string
  tenant_slug: string
  plan_code: PlanCode
  enabled_features: FeatureKey[]
  active_site_tenant_id: string
  available_sites: SiteOption[]
}

export const getAuthSession = () => api.get<AuthSession>('/auth/session', { timeout: 8_000 })
export const updateTenantPlan = (plan_code: PlanCode) =>
  api.patch<AuthSession>('/auth/session/plan', { plan_code })
export interface ActiveSiteSwitchResponse {
  access_token: string
  token_type: string
  expires_in_seconds: number
  refresh_token?: string
  refresh_expires_in_seconds?: number
  active_site_tenant_id: string
  available_sites: SiteOption[]
}
export const switchActiveSite = (tenant_id: string) =>
  api.patch<ActiveSiteSwitchResponse>('/auth/session/site', { tenant_id })

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
  refresh_token?: string
  refresh_expires_in_seconds?: number
}
export const signup = (data: {
  tenant_name: string
  tenant_slug: string
  email: string
  full_name: string
  password: string
  plan_code?: PlanCode
}) => api.post<SignupResponse>('/auth/signup', data)

export const bootstrap = (data: { tenant_name: string; tenant_slug: string; owner_email: string; owner_password: string; owner_full_name?: string }) =>
  api.post('/auth/bootstrap', data)

export interface ParentAccountSite {
  tenant_id: string
  tenant_slug: string
  tenant_name: string
  owner_user_id: string
  owner_email: string
  owner_full_name: string
}

export interface ParentAccountSummary {
  parent_account_id: string
  parent_account_name: string
  owner_email: string
  sites: ParentAccountSite[]
}

export interface ParentAccountActivityEvent {
  id: string
  parent_account_id: string
  tenant_id?: string
  actor_user_id?: string
  actor_email?: string
  event_type: string
  event_summary: string
  created_at: string
}

export const getMyParentAccount = () => api.get<ParentAccountSummary>('/parent-accounts/me')
export const listParentAccountActivity = (limit = 50) =>
  api.get<ParentAccountActivityEvent[]>('/parent-accounts/me/activity', { params: { limit } })
export const linkTenantToParentAccount = (payload: { tenant_slug: string; owner_email: string }) =>
  api.post<ParentAccountSummary>('/parent-accounts/me/link-tenant', payload)
export const createTenantFromParentAccount = (payload: { tenant_name: string; tenant_slug: string; plan_code?: PlanCode }) =>
  api.post<ParentAccountSummary>('/parent-accounts/me/create-tenant', payload)
export const unlinkTenantFromParentAccount = (tenant_id: string) =>
  api.delete<ParentAccountSummary>(`/parent-accounts/me/sites/${tenant_id}`)

// ── Customers ─────────────────────────────────────────────────────────────────
export interface Customer {
  id: string; tenant_id: string; full_name: string
  email?: string; phone?: string; address?: string; notes?: string; created_at: string
}

// ── Customer Accounts (Fleet/B2B) ─────────────────────────────────────────────
export type FleetAccountType = 'Dealership' | 'Rental Fleet' | 'Government Fleet' | 'Corporate Fleet' | 'Car Auctions' | 'Other'
export type FleetBillingCycle = 'Monthly' | 'Fortnightly' | 'Weekly'

export interface CustomerAccount {
  id: string
  tenant_id: string
  name: string
  account_code?: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  billing_address?: string
  payment_terms_days: number
  notes?: string
  is_active: boolean
  created_at: string
  customer_ids: string[]
  // Fleet/Dealer fields
  account_type?: FleetAccountType
  fleet_size?: number
  primary_contact_name?: string
  primary_contact_phone?: string
  billing_cycle?: FleetBillingCycle
  credit_limit?: number
  account_notes?: string
}

export interface CustomerAccountCreate {
  name: string
  account_code?: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  billing_address?: string
  payment_terms_days?: number
  notes?: string
  // Fleet/Dealer fields
  account_type?: FleetAccountType
  fleet_size?: number
  primary_contact_name?: string
  primary_contact_phone?: string
  billing_cycle?: FleetBillingCycle
  credit_limit?: number
  account_notes?: string
}

const CUSTOMER_ACCOUNTS_TIMEOUT_MS = 8_000
export const listCustomerAccounts = () =>
  api.get<CustomerAccount[]>('/customer-accounts', { timeout: CUSTOMER_ACCOUNTS_TIMEOUT_MS })
export const createCustomerAccount = (data: CustomerAccountCreate) => api.post<CustomerAccount>('/customer-accounts', data)
export const updateCustomerAccount = (id: string, data: Partial<CustomerAccountCreate>) => api.patch<CustomerAccount>(`/customer-accounts/${id}`, data)
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
export const getWatch = (id: string) => api.get<Watch>(`/watches/${id}`)
export const listWatchBrands = () => api.get<string[]>('/watch-brands')
export const createWatch = (data: Omit<Watch, 'id' | 'tenant_id' | 'created_at'>) =>
  api.post<Watch>('/watches', data)

// ── Prospects (Google Places) ───────────────────────────────────────────────
export interface Prospect {
  name: string
  address: string
  phone?: string
  website?: string
  rating?: number
  review_count?: number
  category: string
  place_id: string
}

export interface ProspectSearchResponse {
  results: Prospect[]
  total: number
  category: string
}

export const listProspectCategories = () => api.get<{ categories: { key: string; label: string }[] }>('/prospects/categories')
export const searchProspects = (category: string) => api.get<ProspectSearchResponse>('/prospects/search', { params: { category } })

// ── Repair Jobs ───────────────────────────────────────────────────────────────
export type JobStatus = 'awaiting_quote' | 'awaiting_go_ahead' | 'go_ahead' | 'no_go' | 'working_on' | 'awaiting_parts' | 'parts_to_order' | 'sent_to_labanda' | 'quoted_by_labanda' | 'service' | 'completed' | 'awaiting_collection' | 'collected' | 'en_route' | 'on_site'
export interface RepairJob {
  id: string; tenant_id: string; watch_id: string; assigned_user_id?: string; customer_account_id?: string
  job_number: string; status_token: string; title: string; description?: string; priority: string
  status: JobStatus; salesperson?: string; collection_date?: string; deposit_cents: number; pre_quote_cents: number; cost_cents: number; created_at: string
}
export const listJobs = () => api.get<RepairJob[]>('/repair-jobs')
export const getJob = (id: string) => api.get<RepairJob>(`/repair-jobs/${id}`)
export const deleteJob = (id: string) => api.delete(`/repair-jobs/${id}`)
export interface RepairJobCreatePayload {
  watch_id: string
  assigned_user_id?: string
  customer_account_id?: string
  title: string
  description?: string
  priority: string
  status?: JobStatus
  salesperson?: string
  collection_date?: string
  deposit_cents: number
  pre_quote_cents: number
  cost_cents: number
}
export const createJob = (data: RepairJobCreatePayload) =>
  api.post<RepairJob>('/repair-jobs', data)
export const updateJob = (id: string, data: {
  customer_account_id?: string | null
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
export const submitQuoteDecision = (token: string, decision: 'approved' | 'declined', signatureDataUrl?: string | null) =>
  axios.post(`/v1/public/quotes/${token}/decision`, { decision, ...(signatureDataUrl ? { signature_data_url: signatureDataUrl } : {}) })

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

export interface PublicShoeJobStatus {
  job_number: string
  status: string
  title: string
  description?: string
  priority: string
  deposit_cents: number
  estimated_total_cents: number
  created_at: string
  shoe: {
    shoe_type?: string
    brand?: string
    color?: string
  }
  items: Array<{
    item_name: string
    quantity: number
    unit_price_cents: number | null
    notes?: string
  }>
}

export const getPublicShoeJobStatus = (token: string) =>
  axios.get<PublicShoeJobStatus>(`/v1/public/shoe-jobs/${token}`)

// ── Stocktake ────────────────────────────────────────────────────────────────
export interface StockItem {
  id: string
  tenant_id: string
  item_code: string
  group_code: string
  group_name?: string
  item_description?: string
  description2?: string
  description3?: string
  full_description?: string
  unit_description?: string
  pack_description?: string
  pack_qty: number
  cost_price_cents: number
  retail_price_cents: number
  system_stock_qty: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface StockImportSummaryResponse {
  imported: number
  created: number
  updated: number
  sources: Record<string, number>
  sheet_names: string[]
}

export interface StocktakeProgress {
  counted_items: number
  total_items: number
}

export type StocktakeStatus = 'draft' | 'in_progress' | 'completed' | 'approved'

export interface StocktakeSession {
  id: string
  tenant_id: string
  name: string
  status: StocktakeStatus
  created_by_user_id?: string
  completed_by_user_id?: string
  group_code_filter?: string
  group_name_filter?: string
  search_filter?: string
  notes?: string
  created_at: string
  completed_at?: string
  progress: StocktakeProgress
}

export interface StocktakeLine {
  id: string
  stocktake_session_id: string
  stock_item_id: string
  expected_qty: number
  counted_qty?: number | null
  variance_qty?: number | null
  variance_value_cents?: number | null
  counted_by_user_id?: string
  counted_at?: string
  notes?: string
  item_code: string
  group_code: string
  group_name?: string
  item_description?: string
  full_description?: string
  system_stock_qty: number
  cost_price_cents: number
  retail_price_cents: number
}

export interface StocktakeSessionDetail extends StocktakeSession {
  lines: StocktakeLine[]
}

export interface StocktakeGroupSummary {
  group_code: string
  group_name?: string
  item_count: number
  counted_count: number
  variance_count: number
  total_variance_qty: number
  total_variance_value_cents: number
}

export interface StocktakeReport {
  session: StocktakeSession
  matched_item_count: number
  missing_item_count: number
  over_count_item_count: number
  total_variance_qty: number
  total_variance_value_cents: number
  groups: StocktakeGroupSummary[]
}

export const importStockFile = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post<StockImportSummaryResponse>('/stock/import', formData)
}

export const listStockItems = (params?: { search?: string; group_code?: string; group_name?: string; hide_zero_stock?: boolean }) =>
  api.get<StockItem[]>('/stock/items', { params })

export const getStockItem = (id: string) => api.get<StockItem>(`/stock/items/${id}`)

export const createStocktake = (payload: {
  name: string
  group_code?: string
  group_name?: string
  search?: string
  hide_zero_stock?: boolean
  notes?: string
}) => api.post<StocktakeSession>('/stocktakes', payload)

export const listStocktakes = (status?: StocktakeStatus) =>
  api.get<StocktakeSession[]>('/stocktakes', { params: status ? { status } : undefined })

export const deleteStocktake = (id: string) => api.delete(`/stocktakes/${id}`)

export const getStocktake = (id: string, params?: {
  search?: string
  group_code?: string
  group_name?: string
  hide_zero_stock?: boolean
  hide_counted?: boolean
}) => api.get<StocktakeSessionDetail>(`/stocktakes/${id}`, { params })

export const saveStocktakeLines = (id: string, lines: Array<{ stock_item_id: string; counted_qty: number; notes?: string; allow_negative?: boolean }>) =>
  api.post<StocktakeLine[]>(`/stocktakes/${id}/lines`, { lines })

export const updateStocktakeLine = (id: string, lineId: string, payload: { counted_qty?: number; notes?: string; allow_negative?: boolean }) =>
  api.patch<StocktakeLine>(`/stocktakes/${id}/lines/${lineId}`, payload)

export const completeStocktake = (id: string) => api.post<StocktakeReport>(`/stocktakes/${id}/complete`)
export const getStocktakeReport = (id: string) => api.get<StocktakeReport>(`/stocktakes/${id}/report`)
export const exportStocktake = (id: string, format: 'csv' | 'xlsx') =>
  api.get<Blob>(`/stocktakes/${id}/export`, { params: { format }, responseType: 'blob' })

export const getPublicShoeJobQrUrl = (token: string) =>
  `/v1/public/shoe-jobs/${token}/qr`

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
  shoe_repair_job_id?: string; auto_key_job_id?: string
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
export const listShoeAttachments = (shoeRepairJobId: string) =>
  api.get<Attachment[]>('/attachments', { params: { shoe_repair_job_id: shoeRepairJobId } })
export const listAutoKeyAttachments = (autoKeyJobId: string) =>
  api.get<Attachment[]>('/attachments', { params: { auto_key_job_id: autoKeyJobId } })
export const uploadAutoKeyAttachment = (file: File, autoKeyJobId: string, label?: string) => {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams({ auto_key_job_id: autoKeyJobId })
  if (label) params.append('label', label)
  return api.post<Attachment>(`/attachments?${params.toString()}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
export const uploadShoeAttachment = (file: File, shoeRepairJobId: string, label?: string) => {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams({ shoe_repair_job_id: shoeRepairJobId })
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

// ── SMS Log (Messages) ────────────────────────────────────────────────────────
export interface SmsLogEntry {
  id: string; to_phone: string; body: string; event: string; status: string; created_at: string
}
export const getSmsLog = (jobId: string) =>
  api.get<SmsLogEntry[]>(`/repair-jobs/${jobId}/sms-log`)

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
export const importCsv = (
  file: File,
  options?: { replaceExisting?: boolean; clearTabs?: string[] }
) => {
  const form = new FormData()
  form.append('file', file)
  const params = []
  if (options?.replaceExisting) params.push('replace_existing=true')
  if (options?.clearTabs && options.clearTabs.length > 0) {
    for (const tab of options.clearTabs) params.push(`clear_tabs=${encodeURIComponent(tab)}`)
  }
  const query = params.length ? `?${params.join('&')}` : ''
  return api.post<CsvImportResult>(`/import/csv${query}`, form, {
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
// ── Reports Trends ────────────────────────────────────────────────────────────
export interface ReportsTrendMonth {
  month: string
  jobs_opened: number
  revenue_cents: number
}
export interface ReportsTrends {
  months: ReportsTrendMonth[]
}
export const getReportsTrends = (months = 6) =>
  api.get<ReportsTrends>('/reports/trends', { params: { months } })

export interface ReportsWidgets {
  overdue_jobs_count: number
  quotes_pending_7d_count: number
  overdue_invoices_count: number
}
export const getReportsWidgets = () => api.get<ReportsWidgets>('/reports/widgets')

// Export CSV (returns blob)
export const getExportJobsCsv = () => api.get<Blob>('/reports/export/jobs', { responseType: 'blob' })
export const getExportCustomersCsv = () => api.get<Blob>('/reports/export/customers', { responseType: 'blob' })
export const getExportInvoicesCsv = () => api.get<Blob>('/reports/export/invoices', { responseType: 'blob' })

export interface AutoKeySummary {
  jobs_by_tech: { tech_id: string; tech_name: string; job_count: number; revenue_cents: number }[]
  job_type_breakdown: Record<string, number>
  total_jobs: number
  total_revenue_cents: number
}
export const getAutoKeySummary = () => api.get<AutoKeySummary>('/reports/auto-key-summary')

export interface AutoKeyReports {
  date_from: string
  date_to: string
  summary: {
    total_jobs: number
    total_revenue_cents: number
    avg_job_value_cents: number
    completed_jobs: number
    mobile_count: number
    mobile_pct: number
    shop_count: number
    shop_pct: number
  }
  jobs_by_type: { job_type: string; jobs: number; revenue_cents: number; avg_value_cents: number }[]
  jobs_by_tech: { tech_id: string; tech_name: string; job_count: number; revenue_cents: number }[]
  jobs_by_status: { status: string; label: string; count: number }[]
  week_on_week: { week_label: string; jobs: number; revenue_cents: number }[]
}
export const getAutoKeyReports = (params: { date_from?: string; date_to?: string }) =>
  api.get<AutoKeyReports>('/reports/auto-key-reports', { params })
export const sendAutoKeyDayBeforeReminders = () =>
  api.post<{ techs_notified: number; customers_notified: number }>('/auto-key-jobs/send-day-before-reminders')

export const sendAutoKeyArrivalSms = (jobId: string, time_window: string) =>
  api.post<{ sent: boolean }>(`/auto-key-jobs/${jobId}/send-arrival-sms`, { time_window })

export const getExportMyData = () => api.get<Record<string, unknown>>('/auth/export-my-data')

// ── Tenant Activity ───────────────────────────────────────────────────────────
export interface TenantActivityEvent {
  id: string
  tenant_id: string
  actor_user_id?: string | null
  actor_email?: string | null
  entity_type: string
  entity_id?: string | null
  event_type: string
  event_summary: string
  created_at: string
}
export const getTenantActivity = (limit = 50) =>
  api.get<TenantActivityEvent[]>('/reports/activity', { params: { limit } })

// ── Inbox (alerts) ───────────────────────────────────────────────────────────
export const getInbox = (limit = 50) =>
  api.get<TenantActivityEvent[]>('/inbox', { params: { limit } })
export const deleteInboxEvent = (eventId: string) =>
  api.delete(`/inbox/${eventId}`)
export const listUsers = () => api.get<TenantUser[]>('/users')
// ── Billing ───────────────────────────────────────────────────────────────────
export interface BillingPlanLimits {
  max_users: number
  max_repair_jobs: number
  max_shoe_jobs: number
  max_auto_key_jobs: number
}
export interface BillingLimitsUsage {
  users: number
  repair_jobs: number
  shoe_jobs: number
  auto_key_jobs: number
}
export interface BillingLimitsResponse {
  plan_code: string
  limits: BillingPlanLimits
  usage: BillingLimitsUsage
  stripe_configured: boolean
  stripe_subscription_id?: string | null
  stripe_customer_id?: string | null
}
export const getBillingLimits = () => api.get<BillingLimitsResponse>('/billing/limits')
export const getBillingPortalUrl = () => api.get<{ url: string }>('/billing/portal-url')
export const createBillingCheckout = (price_id: string) =>
  api.post<{ checkout_url: string }>('/billing/checkout', { price_id })
export const createBillingCheckoutForPlan = (plan_code: PlanCode) =>
  api.post<{ checkout_url: string }>('/billing/checkout/plan', { plan_code })

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

export type ShoeRepairComplexity = 'simple' | 'standard' | 'complex'

export interface ShoeCatalogueItem {
  key: string
  name: string
  price: number | null
  price_cents: number | null
  pricing_type: ShoePricingType
  group_id: string
  group_label: string
  complexity?: ShoeRepairComplexity
  estimated_days_min?: number
  estimated_days_max?: number
  notes?: string
  includes?: string[]
  applicable_shoe_types?: string[]
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

// ── Watch Catalogue ───────────────────────────────────────────────────────────
export interface WatchCatalogueItem {
  key: string
  name: string
  price: number
  price_cents: number
  pricing_type: string
  group_id?: string
  group_label?: string
  notes?: string
}

export interface WatchCatalogueGroup {
  id: string
  label: string
}

export interface WatchMovement {
  key: string
  name: string
  purchase_cost_cents: number
  fixed_price_cents?: number
  margin_percent?: number
  quote_cents?: number
}

export interface WatchMovementsResponse {
  currency: string
  default_margin_percent: number
  movements: WatchMovement[]
}

export const listWatchCatalogueGroups = () =>
  api.get<WatchCatalogueGroup[]>('/watch-catalogue/groups')

export const searchWatchCatalogueItems = (params?: { q?: string; group?: string }) =>
  api.get<WatchCatalogueItem[]>('/watch-catalogue/items', { params })

export interface WatchRepairsConfig {
  combos: Array<{ keys?: string[]; total_cents?: number; battery_key?: string; band_keys?: string[]; band_discount_percent?: number }>
  currency: string
}
export const getWatchRepairsConfig = () =>
  api.get<WatchRepairsConfig>('/watch-catalogue/repairs-config')

export const listWatchMovements = () =>
  api.get<WatchMovementsResponse>('/watch-catalogue/movements')

export const getWatchMovementQuote = (key: string) =>
  api.get<{ key: string; name: string; quote_cents: number }>(`/watch-catalogue/movements/${key}/quote`)

// ── Custom Services (tenant-defined watch/shoe) ─────────────────────────────────
export interface CustomServiceItem {
  key: string
  name: string
  price: number
  price_cents: number
  pricing_type: string
  group_id: string
  group_label: string
  notes?: string
}

export const listCustomServices = (type: 'watch' | 'shoe') =>
  api.get<CustomServiceItem[]>('/custom-services', { params: { service_type: type } })

export const createCustomService = (data: {
  service_type: 'watch' | 'shoe'
  name: string
  group_id?: string
  group_label?: string
  price_cents: number
  pricing_type?: string
  notes?: string
}) =>
  api.post<CustomServiceItem>('/custom-services', {
    ...data,
    group_id: data.group_id ?? 'custom',
    group_label: data.group_label ?? 'Custom',
    pricing_type: data.pricing_type ?? 'fixed',
  })

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

// ── Mobile Services (auto_key) Jobs ──────────────────────────────────────────
export type AutoKeyProgrammingStatus = 'pending' | 'in_progress' | 'programmed' | 'failed' | 'not_required'

export interface AutoKeyJob {
  id: string
  tenant_id: string
  customer_id: string
  assigned_user_id?: string
  customer_account_id?: string
  job_number: string
  status_token: string
  title: string
  description?: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number
  registration_plate?: string
  vin?: string
  key_type?: string
  blade_code?: string
  chip_type?: string
  tech_notes?: string
  key_quantity: number
  programming_status: AutoKeyProgrammingStatus
  priority: 'low' | 'normal' | 'high' | 'urgent'
  status: JobStatus
  salesperson?: string
  collection_date?: string
  deposit_cents: number
  cost_cents: number
  created_at: string
  /** ServiceM8-style: when job is scheduled */
  scheduled_at?: string
  /** For mobile jobs; address where tech visits */
  job_address?: string
  /** "mobile" | "shop" */
  job_type?: string
  /** Route order for same-day jobs (lower = first) */
  visit_order?: number
}

export interface AutoKeyJobCreatePayload {
  customer_id: string
  customer_account_id?: string
  assigned_user_id?: string
  title: string
  description?: string
  scheduled_at?: string
  job_address?: string
  job_type?: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number
  registration_plate?: string
  vin?: string
  key_type?: string
  key_quantity: number
  programming_status: AutoKeyProgrammingStatus
  priority: 'low' | 'normal' | 'high' | 'urgent'
  status: JobStatus
  salesperson?: string
  collection_date?: string
  deposit_cents: number
  cost_cents: number
}

export const listAutoKeyJobs = (params?: { date_from?: string; date_to?: string; include_unscheduled?: boolean; assigned_user_id?: string; customer_id?: string; status?: string; active_only?: boolean }) =>
  api.get<AutoKeyJob[]>('/auto-key-jobs', params ? { params } : undefined)

export interface VehicleLookupResult {
  found: boolean
  make: string | null
  model: string | null
  year: number | null
  vin: string | null
  registration_plate: string
  state: string
}
export const vehicleLookup = (plate: string, state: string) =>
  api.get<VehicleLookupResult>('/vehicle-lookup', { params: { plate, state } })
export const getAutoKeyJob = (id: string) => api.get<AutoKeyJob>(`/auto-key-jobs/${id}`)
export const createAutoKeyJob = (data: AutoKeyJobCreatePayload) => api.post<AutoKeyJob>('/auto-key-jobs', data)
export interface AutoKeyJobUpdatePayload extends Omit<Partial<AutoKeyJobCreatePayload>, 'customer_account_id' | 'assigned_user_id' | 'scheduled_at' | 'job_address' | 'job_type' | 'visit_order' | 'key_type' | 'blade_code' | 'chip_type' | 'tech_notes'> {
  customer_account_id?: string | null
  assigned_user_id?: string | null
  scheduled_at?: string | null
  job_address?: string | null
  job_type?: string | null
  visit_order?: number | null
  key_type?: string | null
  blade_code?: string | null
  chip_type?: string | null
  tech_notes?: string | null
}
export const updateAutoKeyJob = (id: string, data: AutoKeyJobUpdatePayload) =>
  api.patch<AutoKeyJob>(`/auto-key-jobs/${id}`, data)
export const updateAutoKeyJobStatus = (id: string, status: JobStatus, note?: string) =>
  api.post<AutoKeyJob>(`/auto-key-jobs/${id}/status`, { status, note })
export const deleteAutoKeyJob = (id: string) => api.delete(`/auto-key-jobs/${id}`)

export interface AutoKeyQuoteLineItem {
  id: string
  auto_key_quote_id: string
  description: string
  quantity: number
  unit_price_cents: number
  total_price_cents: number
}

export interface AutoKeyQuote {
  id: string
  tenant_id: string
  auto_key_job_id: string
  status: string
  subtotal_cents: number
  tax_cents: number
  total_cents: number
  currency: string
  sent_at?: string
  created_at: string
  line_items: AutoKeyQuoteLineItem[]
}

export interface AutoKeyInvoice {
  id: string
  tenant_id: string
  auto_key_job_id: string
  auto_key_quote_id?: string
  invoice_number: string
  status: string
  subtotal_cents: number
  tax_cents: number
  total_cents: number
  currency: string
  payment_method?: string
  paid_at?: string
  created_at: string
}

export interface AutoKeyQuoteCreatePayload {
  line_items: Array<{
    description: string
    quantity: number
    unit_price_cents: number
  }>
  tax_cents: number
}

export const listAutoKeyQuotes = (jobId: string) => api.get<AutoKeyQuote[]>(`/auto-key-jobs/${jobId}/quotes`)
export const createAutoKeyQuote = (jobId: string, payload: AutoKeyQuoteCreatePayload) =>
  api.post<AutoKeyQuote>(`/auto-key-jobs/${jobId}/quotes`, payload)
export const sendAutoKeyQuote = (quoteId: string) => api.post<AutoKeyQuote>(`/auto-key-jobs/quotes/${quoteId}/send`)
export const listAutoKeyInvoices = (jobId: string) => api.get<AutoKeyInvoice[]>(`/auto-key-jobs/${jobId}/invoices`)
export const createAutoKeyInvoiceFromQuote = (jobId: string, quoteId: string) =>
  api.post<AutoKeyInvoice>(`/auto-key-jobs/${jobId}/invoices/from-quote/${quoteId}`)
export const updateAutoKeyInvoice = (jobId: string, invoiceId: string, data: { status?: string; payment_method?: string }) =>
  api.patch<AutoKeyInvoice>(`/auto-key-jobs/${jobId}/invoices/${invoiceId}`, data)

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

export interface ShoeRepairJobItemInput {
  catalogue_key: string
  catalogue_group: string
  item_name: string
  pricing_type: ShoePricingType
  unit_price_cents: number | null
  quantity?: number
  notes?: string
}

export interface ShoeRepairJobShoe {
  id: string
  shoe_id: string
  shoe?: Shoe
  sort_order: number
}

export interface ShoeRepairJob {
  id: string
  tenant_id: string
  shoe_id: string
  customer_account_id?: string
  shoe?: Shoe
  extra_shoes: ShoeRepairJobShoe[]
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
  /** Derived from services: simple | standard | complex */
  complexity?: ShoeRepairComplexity
  estimated_days_min?: number
  estimated_days_max?: number
  /** Queue-based: est. date ready (FIFO from jobs ahead) */
  estimated_ready_by?: string
}

export interface ShoeRepairJobCreatePayload {
  shoe_id: string
  customer_account_id?: string
  title: string
  description?: string
  priority?: string
  status?: string
  salesperson?: string
  collection_date?: string
  deposit_cents?: number
  cost_cents?: number
  items: ShoeRepairJobItemInput[]
}

export const listShoeRepairJobs = (status?: string) =>
  api.get<ShoeRepairJob[]>('/shoe-repair-jobs', status ? { params: { status } } : undefined)

export const getShoeRepairJob = (id: string) =>
  api.get<ShoeRepairJob>(`/shoe-repair-jobs/${id}`)

export const deleteShoeRepairJob = (id: string) =>
  api.delete(`/shoe-repair-jobs/${id}`)

export const createShoeRepairJob = (data: ShoeRepairJobCreatePayload) =>
  api.post<ShoeRepairJob>('/shoe-repair-jobs', data)

export const updateShoeRepairJob = (id: string, data: Partial<{
  customer_account_id: string | null
  title: string; description: string; priority: string
  salesperson: string; collection_date: string
  deposit_cents: number; cost_cents: number
}>) => api.patch<ShoeRepairJob>(`/shoe-repair-jobs/${id}`, data)

export const updateShoeRepairJobStatus = (id: string, status: string, note?: string) =>
  api.post<ShoeRepairJob>(`/shoe-repair-jobs/${id}/status`, { status, note })

export const addShoeToJob = (jobId: string, shoeId: string) =>
  api.post<ShoeRepairJob>(`/shoe-repair-jobs/${jobId}/shoes`, { shoe_id: shoeId })

export const appendShoeRepairJobItems = (jobId: string, items: ShoeRepairJobItemInput[]) =>
  api.post<ShoeRepairJob>(`/shoe-repair-jobs/${jobId}/items`, { items })

export const removeShoeFromJob = (jobId: string, entryId: string) =>
  api.delete<ShoeRepairJob>(`/shoe-repair-jobs/${jobId}/shoes/${entryId}`)

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

// ── Customer Accounts (B2B) ──────────────────────────────────────────────────
export interface CustomerAccount {
  id: string
  tenant_id: string
  name: string
  account_code?: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  billing_address?: string
  payment_terms_days: number
  notes?: string
  is_active: boolean
  created_at: string
  customer_ids: string[]
}

export interface CustomerAccountCreatePayload {
  name: string
  account_code?: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  billing_address?: string
  payment_terms_days?: number
  notes?: string
}

export interface CustomerAccountStatementLine {
  source_type: 'watch' | 'shoe' | 'auto_key'
  source_job_id: string
  job_number: string
  description: string
  amount_cents: number
}

export interface CustomerAccountStatement {
  customer_account_id: string
  period_year: number
  period_month: number
  lines: CustomerAccountStatementLine[]
  subtotal_cents: number
}

export interface CustomerAccountInvoice {
  id: string
  tenant_id: string
  customer_account_id: string
  invoice_number: string
  period_year: number
  period_month: number
  status: string
  subtotal_cents: number
  tax_cents: number
  total_cents: number
  currency: string
  created_at: string
  lines: CustomerAccountStatementLine[]
}

export interface CustomerAccountMonthlyInvoicePayload {
  period_year: number
  period_month: number
  tax_cents?: number
}

export const addCustomerToAccount = (accountId: string, customerId: string) =>
  api.post<CustomerAccount>(`/customer-accounts/${accountId}/customers`, { customer_id: customerId })
export const removeCustomerFromAccount = (accountId: string, customerId: string) =>
  api.delete(`/customer-accounts/${accountId}/customers/${customerId}`)
export const getCustomerAccountStatement = (accountId: string, period_year: number, period_month: number) =>
  api.get<CustomerAccountStatement>(`/customer-accounts/${accountId}/statement`, { params: { period_year, period_month } })
export const listCustomerAccountInvoices = (accountId: string) =>
  api.get<CustomerAccountInvoice[]>(`/customer-accounts/${accountId}/invoices`)
export const generateCustomerAccountMonthlyInvoice = (
  accountId: string,
  payload: CustomerAccountMonthlyInvoicePayload,
) => api.post<CustomerAccountInvoice>(`/customer-accounts/${accountId}/invoices/monthly`, payload)
