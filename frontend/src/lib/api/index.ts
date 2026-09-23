import axios from 'axios'
import api, { withApiOrigin, getApiErrorMessage } from './client'

export * from './client'
export { default } from './client'

export interface MultiSiteLoginResponse {
  access_token: string
  token_type?: string
  expires_in_seconds: number
  refresh_token?: string | null
  refresh_expires_in_seconds?: number | null
  active_site_tenant_id: string
  available_sites?: SiteOption[]
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
  | 'booking_only'
  | 'minit_hq'
  | 'pro'
export type FeatureKey =
  | 'watch'
  | 'shoe'
  | 'auto_key'
  | 'customer_accounts'
  | 'multi_site'
  | 'rego_lookup'
  | 'shop_mobile_booking'

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
  /** ``minit`` for Mister Minit network tenants; ``mainspring`` for standard shops. */
  product?: 'minit' | 'mainspring'
  /** When true, render the six-item Minit HQ sidebar (authoritative server signal). */
  is_minit_hq_ui?: boolean
  plan_code: PlanCode
  enabled_features: FeatureKey[]
  active_site_tenant_id: string
  available_sites: SiteOption[]
  signup_payment_pending?: boolean
  /** Mirrors Stripe subscription status: "trialing" | "active" | "past_due" | "canceled" | null */
  subscription_status?: string | null
  /** ISO-8601 UTC string of when the trial ends; null when not trialing */
  trial_end?: string | null
  shop_calendar_today_ymd?: string
  schedule_calendar_timezone?: string
  /** When false, customer SMS for mobile services is off (session mirrors tenant setting). */
  mobile_services_customer_sms_enabled?: boolean
  tenant_business_address?: string | null
}

export const getAuthSession = () => api.get<AuthSession>('/auth/session')
export const updateTenantPlan = (plan_code: PlanCode) =>
  api.patch<AuthSession>('/auth/session/plan', { plan_code })
export interface ActiveSiteSwitchResponse {
  access_token: string
  token_type?: string
  expires_in_seconds: number
  refresh_token?: string | null
  refresh_expires_in_seconds?: number | null
  active_site_tenant_id: string
  available_sites?: SiteOption[]
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

export type NetworkRole = 'hq' | 'retail' | 'operator'
export type ParentRole = 'hq_admin' | 'hq_viewer'

export interface ParentAccountSite {
  tenant_id: string
  tenant_slug: string
  tenant_name: string
  shop_number?: string | null
  area?: string | null
  /** Display name of the site's Region (falls back to the raw TSS string). */
  region?: string | null
  region_id?: string | null
  region_code?: string | null
  plan_code: string
  /** The site's place in the network — independent of what it is billed for. */
  network_role: NetworkRole
  owner_user_id: string
  owner_email: string
  owner_full_name: string
  /** The owner's own mobile, when the franchisee record supplied one. */
  owner_mobile?: string | null
  /** True when the shop still uses the shared HQ login — no franchisee to invite yet. */
  owner_is_shared_hq_login?: boolean
  /** Tenant shop-identity email used when sending an owner invite. */
  shop_email?: string | null
  /** Tenant shop-identity phone used when SMS-ing an owner invite. */
  shop_phone?: string | null
}

export interface ParentAccountUser {
  user_id: string
  tenant_id: string
  tenant_slug: string
  email: string
  full_name: string
  tenant_role: string
  role: ParentRole
  /** Set for a regional manager: access is limited to this region. */
  region_id?: string | null
  region_name?: string | null
  /** explicit (granted) | hq_site (implied by being in the HQ tenant) | owner_email */
  source: 'explicit' | 'hq_site' | 'owner_email'
  is_active: boolean
  created_at: string
}

export interface ParentEnterShopResponse {
  access_token: string
  expires_in_seconds: number
  tenant_id: string
  tenant_slug: string
  tenant_name: string
  acting_as_user_id: string
  acting_as_email: string
}

export interface Region {
  id: string
  code: string
  name: string
  manager_name?: string | null
  manager_email?: string | null
  manager_phone?: string | null
  escalation_email?: string | null
  notes?: string | null
  weekly_report_opt_in: boolean
  last_weekly_report_sent_at?: string | null
  site_count: number
  created_at: string
}

export type RegionInput = {
  name: string
  code?: string
  manager_name?: string | null
  manager_email?: string | null
  manager_phone?: string | null
  escalation_email?: string | null
  notes?: string | null
  weekly_report_opt_in?: boolean
}

export interface RegionWeekAnnotation {
  id: string
  region_id: string
  region_name?: string | null
  week: number
  event_type: string
  note: string
  exclude_from_baselines: boolean
  created_at: string
  updated_at: string
}

export interface RegionShopRow {
  shop_number: string
  tenant_id: string | null
  shop_name: string
  area_name: string | null
  reported: boolean
  sales: number | null
  previous_sales: number | null
  delta: number | null
  delta_pct: number | null
  customers: number | null
  jobs: number | null
  avg_sale: number | null
  rank_in_region: number | null
  rank_in_network: number | null
  zscore: number | null
  anomaly: 'high' | 'low' | null
  watch: 'high' | 'low' | null
  baseline_weeks: number
  target: number | null
  target_variance: number | null
  target_met: boolean | null
}

export interface RegionCockpitRow extends VswtKpiDef {
  current: number | null
  previous: number | null
  rolling_4: number | null
  rolling_13: number | null
  rolling_52: number | null
  rolling_counts: Record<string, number>
  last_year: number | null
  comparison: number | null
  delta: number | null
  delta_pct: number | null
  network_avg: number | null
  rank: number | null
  previous_rank: number | null
  rank_change: number | null
  zscore: number | null
  anomaly: 'high' | 'low' | null
  watch: 'high' | 'low' | null
  baseline_weeks: number
}

export interface RegionCockpit {
  available: true
  region: {
    id: string
    code: string
    name: string
    manager_name: string | null
    manager_email: string | null
    weekly_report_opt_in: boolean
    last_weekly_report_sent_at: string | null
  }
  week: number
  previous_week: number | null
  weeks: number[]
  comparison: VswtComparison
  shop_count: number
  shops_reported: number
  region_count: number
  rows: RegionCockpitRow[]
  headline: RegionCockpitRow[]
  drivers: { category_sales: { key: string; label: string; current: number | null; previous: number | null; delta: number | null; share_of_sales: number | null }[] }
  shops: RegionShopRow[]
  movers: { up: RegionShopRow[]; down: RegionShopRow[] }
  anomalies: RegionShopRow[]
  alerts: VswtAlert[]
  narrative: string
  target_attainment: { shops_with_target: number; shops_met: number; total_target: number | null; total_current: number | null; attainment_pct: number | null }
  leaderboard: { region_id: string; region_name: string; sales: number | null; customers: number | null; shops: number; rank: number | null; is_me: boolean; delta_pct: number | null }[]
  annotations: RegionWeekAnnotation[]
  excluded_weeks: number[]
}
export type RegionCockpitUnavailable = { available: false; reason: 'no_data' | 'no_shops' }

export const getRegionCockpit = (regionId: string, params: { week?: number; comparison?: VswtComparison } = {}) =>
  api.get<RegionCockpit | RegionCockpitUnavailable>(`/parent-accounts/me/regions/${regionId}/cockpit`, {
    params: {
      ...(params.week ? { week: params.week } : {}),
      ...(params.comparison ? { comparison: params.comparison } : {}),
    },
  })
export const listRegionAnnotations = (regionId: string) =>
  api.get<RegionWeekAnnotation[]>(`/parent-accounts/me/regions/${regionId}/annotations`)
export const putRegionAnnotation = (
  regionId: string,
  payload: { week: number; event_type: string; note: string; exclude_from_baselines: boolean },
) => api.put<RegionWeekAnnotation>(`/parent-accounts/me/regions/${regionId}/annotations`, payload)
export const deleteRegionAnnotation = (regionId: string, annotationId: string) =>
  api.delete<{ deleted: string }>(`/parent-accounts/me/regions/${regionId}/annotations/${annotationId}`)
export type RegionTargetStrategy = 'last_year_plus_pct' | 'region_median' | 'previous_week'
export const fillRegionTargets = (
  regionId: string,
  payload: { strategy: RegionTargetStrategy; pct?: number; metric_keys?: string[]; week?: number },
) => api.post<{ strategy: string; week: number; shops_updated: number; targets_written: number; shops_skipped_no_data: number }>(
  `/parent-accounts/me/regions/${regionId}/targets/fill`, payload,
)
export const sendRegionReportNow = (regionId: string) =>
  api.post<{ sent: boolean; to: string }>(`/parent-accounts/me/regions/${regionId}/report/send-now`)

export function formatTenantLabel(name: string, shopNumber?: string | null): string {
  const base = name.trim() || 'Unknown'
  const num = shopNumber?.trim()
  return num ? `${base} (#${num})` : base
}

export interface ParentAccountSummary {
  parent_account_id: string
  parent_account_name: string
  owner_email: string
  /** The caller's own network role. */
  my_role?: ParentRole | null
  /** Set when the caller is a regional manager: the one region they can see. */
  my_region_id?: string | null
  site_count: number
  sites: ParentAccountSite[]
  mobile_lead_ingest_public_id?: string | null
  mobile_lead_webhook_secret_configured?: boolean
  mobile_lead_default_tenant_id?: string | null
  /** Link requests this network sent that the shop has not answered yet. */
  pending_link_requests?: NetworkLinkRequest[]
}

/** A network asking to add a shop; the shop's owner accepts or declines. */
export interface NetworkLinkRequest {
  id: string
  parent_account_id: string
  parent_account_name: string
  tenant_id: string
  tenant_slug: string
  tenant_name: string
  status: 'pending' | 'accepted' | 'declined'
  requested_by_email?: string | null
  created_at: string
}

export const listNetworkLinkRequests = () => api.get<NetworkLinkRequest[]>('/network-link-requests')
export const acceptNetworkLinkRequest = (id: string) =>
  api.post<NetworkLinkRequest>(`/network-link-requests/${id}/accept`)
export const declineNetworkLinkRequest = (id: string) =>
  api.post<NetworkLinkRequest>(`/network-link-requests/${id}/decline`)

export interface ParentLeadIngestConfig {
  parent_account_id: string
  mobile_lead_ingest_public_id?: string | null
  mobile_lead_webhook_secret_configured?: boolean
  inbound_email_secret_configured?: boolean
  mobile_lead_default_tenant_id?: string | null
  mobile_lead_escalation_tenant_id?: string | null
  mobile_lead_offer_timeout_minutes?: number
  mobile_lead_max_operator_offers?: number
  mobile_lead_force_hq_dispatch?: boolean
}

export interface ParentAccountSitesPage {
  sites: ParentAccountSite[]
  total: number
  limit: number
  offset: number
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

export const getMyParentAccount = (params?: { include_sites?: boolean }) =>
  api.get<ParentAccountSummary>('/parent-accounts/me', {
    params: { include_sites: params?.include_sites ?? false },
  })
export const getParentLeadIngestConfig = () =>
  api.get<ParentLeadIngestConfig>('/parent-accounts/me/lead-ingest')
export const listParentAccountSites = (params?: {
  limit?: number
  offset?: number
  search?: string
  region?: string
  plan_kind?: 'retail' | 'operator' | 'all'
}) => api.get<ParentAccountSitesPage>('/parent-accounts/me/sites', { params })
export const listParentAccountActivity = (limit = 50, offset = 0) =>
  api.get<ParentAccountActivityEvent[]>('/parent-accounts/me/activity', { params: { limit, offset } })
export const linkTenantToParentAccount = (payload: { tenant_slug: string; owner_email: string; shop_number?: string }) =>
  api.post<ParentAccountSummary>('/parent-accounts/me/link-tenant', payload)
export const createTenantFromParentAccount = (payload: {
  tenant_name: string
  tenant_slug: string
  plan_code?: PlanCode
  shop_number?: string
}) => api.post<ParentAccountSummary>('/parent-accounts/me/create-tenant', payload)
export const unlinkTenantFromParentAccount = (tenant_id: string) =>
  api.delete<ParentAccountSummary>(`/parent-accounts/me/sites/${tenant_id}`)
export const enterLinkedShop = (tenantId: string, reason?: string) =>
  api.post<ParentEnterShopResponse>(`/parent-accounts/me/sites/${tenantId}/enter`, reason ? { reason } : {})
export const updateLinkedSite = (
  tenantId: string,
  payload: {
    network_role?: NetworkRole
    region_id?: string | null
    clear_region?: boolean
    shop_email?: string | null
    shop_phone?: string | null
  },
) => api.patch<ParentAccountSite>(`/parent-accounts/me/sites/${tenantId}`, payload)

export const listParentAccountUsers = () =>
  api.get<ParentAccountUser[]>('/parent-accounts/me/users')
export const grantParentAccountRole = (payload: { user_id?: string; email?: string; role: ParentRole; region_id?: string | null }) =>
  api.put<ParentAccountUser[]>('/parent-accounts/me/users', payload)
export const revokeParentAccountRole = (userId: string) =>
  api.delete<ParentAccountUser[]>(`/parent-accounts/me/users/${userId}`)

export const listRegions = () => api.get<Region[]>('/parent-accounts/me/regions')
export const createRegion = (payload: RegionInput) => api.post<Region>('/parent-accounts/me/regions', payload)
export const updateRegion = (regionId: string, payload: Partial<RegionInput>) =>
  api.patch<Region>(`/parent-accounts/me/regions/${regionId}`, payload)
export const deleteRegion = (regionId: string) => api.delete<Region[]>(`/parent-accounts/me/regions/${regionId}`)

export interface ShopOwnerInvite {
  id: string
  tenant_id: string
  tenant_name: string
  tenant_slug: string
  shop_number?: string | null
  owner_email: string
  owner_mobile?: string | null
  plan_code: PlanCode | string
  status: 'pending' | 'completed' | 'revoked' | 'expired'
  invite_url: string
  expires_at: string
  created_at: string
  completed_at?: string | null
  /** Set on the create response only — whether that call just sent the link. */
  email_sent?: boolean
  sms_sent?: boolean
}

/** Curated plan/tier choices meaningful when inviting a Minit shop owner — must match
 * MINIT_INVITE_PLAN_CODES in backend/app/routes/parent_accounts.py. */
export const MINIT_INVITE_PLAN_OPTIONS: Array<{ code: PlanCode; label: string }> = [
  { code: 'booking_only', label: 'Retail shop — booking only' },
  { code: 'basic_auto_key', label: 'Mobile operator — Basic' },
  { code: 'pro', label: 'Mobile operator — Pro (multi-site)' },
]

/** Send (or reissue) a one-time invite letting a shop set its own login.
 * Pass `planCode` to set the shop's plan/tier at the same time. */
export const createShopOwnerInvite = (tenantId: string, planCode?: PlanCode | string) =>
  api.post<ShopOwnerInvite>(`/parent-accounts/me/sites/${tenantId}/invite`, planCode ? { plan_code: planCode } : {})
export const getShopOwnerInvite = (tenantId: string) =>
  api.get<ShopOwnerInvite | null>(`/parent-accounts/me/sites/${tenantId}/invite`)

export interface ShopOwnerInvitePublic {
  tenant_name: string
  shop_number?: string | null
  masked_email: string
  status: string
  expires_at: string
}

export const getShopOwnerInvitePublic = (token: string) =>
  api.get<ShopOwnerInvitePublic>(`/public/shop-invite/${token}`)
export const completeShopOwnerInvite = (
  token: string,
  payload: { full_name: string; email: string; password: string },
) =>
  api.post<{
    access_token: string
    token_type: string
    expires_in_seconds: number
    refresh_token?: string
    refresh_expires_in_seconds?: number
  }>(`/public/shop-invite/${token}/complete`, payload)

export interface ShopBookingUsageShop {
  tenant_id: string
  tenant_name: string
  shop_number?: string | null
  accepted_bookings_count: number
  pending_count: number
}

export interface ShopBookingUsage {
  month: string
  booking_tenant_count: number
  shops: ShopBookingUsageShop[]
}

export const getParentShopBookingUsage = (month: string) =>
  api.get<ShopBookingUsage>('/parent-accounts/me/shop-booking-usage', { params: { month } })

/** A shopfront starts on booking_only and counts as retail; a mobile operator
 * starts on basic_auto_key and joins the network's operator roll-up. */
export type MinitShopType = 'physical' | 'mobile'

export const MINIT_SHOP_TYPE_OPTIONS: Array<{ value: MinitShopType; label: string }> = [
  { value: 'physical', label: 'Physical shop (shopfront)' },
  { value: 'mobile', label: 'Mobile shop (van operator)' },
]

export const provisionMinitShop = (payload: {
  shop_number: string
  tenant_name: string
  business_address?: string
  shop_type?: MinitShopType
  /** Give the shop its own owner login so an invite reaches the operator.
   * Omit and the shop shares the HQ login until someone fills it in. */
  owner_email?: string
  owner_full_name?: string
  owner_mobile?: string
}) => api.post<ParentAccountSummary>('/parent-accounts/me/provision-shop', payload)

export interface ParentImportShopsResult {
  created_count: number
  updated_count: number
  skipped_count: number
  parsed_count: number
  sheet_name?: string | null
  errors: string[]
}

export const importParentShopsFromXlsx = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<ParentImportShopsResult>('/parent-accounts/me/import-shops', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000, // ~379 shops: bulk DB work can exceed 2 min on cold Postgres
  })
}

export interface DirectoryImportEntry {
  shop_number: string
  name: string
  slug: string
  area: string
  region: string
  address: string
  ownership: string
  owner_email: string
  owner_full_name: string
  owner_source: string
}

export interface DirectoryImportWarning {
  kind: string
  detail: string
}

export interface DirectoryImportSummary {
  hq_parent_found: boolean
  note?: string
  parent_account_id?: string
  parent_account_name?: string
  dry_run?: boolean
  shops?: {
    total_in_export: number
    open: number
    closed_skipped: number
    already_exists: number
    would_create: number
  }
  franchisees?: {
    total_in_export: number
    single_site: number
    multi_site: number
    would_create_parent_accounts: number
    existing_parent_accounts_reused: number
  }
  fallback_to_hq_login?: {
    company_owned_no_franchisee: number
    franchisee_missing_email: number
  }
  would_create_sample?: DirectoryImportEntry[]
  would_create_truncated?: boolean
  already_exists_sample?: DirectoryImportEntry[]
  already_exists_truncated?: boolean
  warnings_sample?: DirectoryImportWarning[]
  warnings_count?: number
  created_tenant_count?: number
  created_tenant_slugs?: string[]
  created_tenant_slugs_truncated?: boolean
  created_owner_count?: number
  created_franchisee_parent_account_count?: number
}

/** Preview (apply=false, default) or apply importing shops + real franchisee owners
 * from a Mister Minit "Organisation Graph" directory HTML export. */
export const importMinitDirectory = (file: File, apply: boolean) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<DirectoryImportSummary>('/parent-accounts/me/import-directory', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params: { apply },
    // A preview only parses and counts — well under a second even for a
    // 1MB export — so anything past a minute means something is wrong and the
    // user should be told, not left watching a spinner. Apply does real work
    // but still dies at the proxy's 120s read limit, so waiting ten minutes
    // for a response that can no longer arrive just hides the failure.
    timeout: apply ? 180000 : 60000,
  })
}

/** Preview (default) or apply filling in franchisee contact details for shops
 * still sharing the HQ login, from the same directory export. */
export const backfillShopOwnerContacts = (file: File, apply: boolean) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<Record<string, unknown>>('/parent-accounts/me/backfill-shop-owner-contacts', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params: { apply },
    timeout: apply ? 180000 : 60000,
  })
}

export interface ParentDashboardBookingSnippet {
  id: string
  customer_name: string
  status: string
  requesting_shop_name: string
  requesting_shop_number?: string | null
  target_operator_name: string
  region?: string | null
  area?: string | null
  created_at: string
}

export interface ParentRegionDashboardStat {
  region: string
  region_id?: string | null
  manager_name?: string | null
  shop_count: number
  bookings_30d: number
  pending: number
  active_shops_30d: number
}

export interface ParentOperationsOverview {
  retail_shop_count: number
  operator_count: number
  pending_bookings: number
  active_mobile_jobs: number
  shops_without_recent_booking: number
  problem_bookings_7d: number
  operators_missing_dispatch_phone: number
  bookings_7d?: number
  accepted_7d?: number
  declined_7d?: number
  bookings_30d?: number
  accepted_30d?: number
  stale_pending_count?: number
  acceptance_rate_7d?: number | null
  region_stats?: ParentRegionDashboardStat[]
  recent_bookings?: ParentDashboardBookingSnippet[]
  attention_items?: ParentTroubleshootingItem[]
}

export interface ParentShopBookingVolume {
  tenant_id: string
  tenant_name: string
  shop_number?: string | null
  total: number
  pending: number
  accepted: number
  declined: number
  cancelled: number
  expired: number
}

export interface ParentShopBookingsReport {
  from_date?: string | null
  to_date?: string | null
  totals: ParentShopBookingVolume
  by_shop?: ParentShopBookingVolume[]
  bookings?: ShopMobileBooking[]
}

export interface ParentMobileJobNetwork {
  id: string
  job_number: string
  status: string
  title: string
  operator_tenant_id: string
  operator_name: string
  operator_shop_number?: string | null
  referring_shop_tenant_id?: string | null
  referring_shop_name?: string | null
  referring_shop_number?: string | null
  shop_mobile_booking_request_id?: string | null
  job_type?: string | null
  commission_lead_source?: string | null
  paid_cents?: number | null
  work_completed_at?: string | null
  scheduled_at?: string | null
  created_at: string
}

export interface ParentMobileJobsReport {
  from_date?: string | null
  to_date?: string | null
  active_count: number
  total_count: number
  has_more?: boolean
  jobs?: ParentMobileJobNetwork[]
}

export interface ParentTroubleshootingItem {
  kind: string
  severity: string
  title: string
  detail: string
  tenant_id?: string | null
  tenant_slug?: string | null
  related_id?: string | null
  created_at?: string | null
}

export const getParentOperationsOverview = () =>
  api.get<ParentOperationsOverview>('/parent-accounts/me/operations/overview')

export const getParentShopBookingsReport = (params?: {
  from_date?: string
  to_date?: string
  status?: string
  shop_tenant_id?: string
  limit?: number
}) => api.get<ParentShopBookingsReport>('/parent-accounts/me/operations/bookings', { params })

export const getParentMobileJobsReport = (params?: {
  from_date?: string
  to_date?: string
  status?: string
  operator_tenant_id?: string
  lead_source?: string
  category?: string
  limit?: number
}) => api.get<ParentMobileJobsReport>('/parent-accounts/me/operations/mobile-jobs', { params })

export interface ShopEmailLeadBucket {
  operator_tenant_id?: string | null
  operator_name: string
  total_count?: number
  new_count?: number
  processed_count?: number
  dismissed_count?: number
  oldest_new_at?: string | null
}
export interface ParentEmailLeadsByShopReport {
  from_date?: string | null
  to_date?: string | null
  total_emails: number
  shops?: ShopEmailLeadBucket[]
}
export const getParentEmailLeadsByShopReport = (params?: { from_date?: string; to_date?: string }) =>
  api.get<ParentEmailLeadsByShopReport>('/parent-accounts/me/operations/email-leads-by-shop', { params })

export const getParentTroubleshooting = (limit = 50) =>
  api.get<{ items: ParentTroubleshootingItem[] }>('/parent-accounts/me/operations/troubleshooting', {
    params: { limit },
  })

export interface MobileKpiOperatorRow {
  operator_tenant_id: string
  operator_name: string
  operator_shop_number?: string | null
  customers_count: number
  jobs_created: number
  jobs_completed: number
  sales_cents: number
  prior_sales_cents: number
  prior_jobs_created: number
  sales_pct_change?: number | null
  avg_sale_cents?: number | null
  jobs_per_customer?: number | null
  paid_customers_count?: number
  category_jobs?: Record<string, number>
  category_sales_cents?: Record<string, number>
  lead_jobs?: Record<string, number>
  lead_sales_cents?: Record<string, number>
  active_jobs: number
  outstanding_cents: number
  enquiries_not_actioned: number
}

export interface MobileKpiPeriod {
  start: string
  end: string
  start_ymd: string
  end_ymd: string
  timezone: string
  generated_at: string
  network: MobileKpiOperatorRow
  operators?: MobileKpiOperatorRow[]
}

export interface MobileKpiLive {
  timezone: string
  generated_at: string
  trade_date: string
  scope?: string
  day?: MobileKpiPeriod | null
  week?: MobileKpiPeriod | null
}

export interface MobileKpiDailyListItem {
  trade_date: string
  compiled_at: string
  operator_count: number
  sales_cents: number
  jobs_created: number
  customers_count: number
}

export interface MobileKpiDailyList {
  timezone: string
  days?: MobileKpiDailyListItem[]
}

export interface MobileKpiDailyDetail {
  trade_date: string
  compiled_at: string
  timezone: string
  report: MobileKpiPeriod
}

export interface MobileKpiWeeklyListItem {
  week_start_ymd: string
  week_end_ymd: string
  compiled_at: string
  emailed_at?: string | null
  operator_count: number
  sales_cents: number
  jobs_created: number
  customers_count: number
}

export interface MobileKpiWeeklyList {
  timezone: string
  weeks?: MobileKpiWeeklyListItem[]
}

export interface MobileKpiWeeklyDetail {
  week_start_ymd: string
  week_end_ymd: string
  compiled_at: string
  emailed_at?: string | null
  timezone: string
  report: MobileKpiPeriod
}

export interface MobileKpiRecipient {
  user_id: string
  email: string
  full_name: string
  role: string
  source: string
  email_mobile_kpi_report: boolean
}

export interface MobileKpiRecipients {
  opt_in: boolean
  last_sent_at?: string | null
  recipients?: MobileKpiRecipient[]
}

export const getParentMobileKpisLive = (scope: 'day' | 'week' | 'all' = 'week') =>
  api.get<MobileKpiLive>('/parent-accounts/me/operations/mobile-kpis/live', { params: { scope } })

export const getParentMobileKpisLiveCsv = (scope: 'day' | 'week' = 'week') =>
  api.get<Blob>('/parent-accounts/me/operations/mobile-kpis/live/csv', { params: { scope }, responseType: 'blob' })

export const getParentMobileKpiDays = () =>
  api.get<MobileKpiDailyList>('/parent-accounts/me/operations/mobile-kpis/days')

export const getParentMobileKpiDay = (tradeDate: string) =>
  api.get<MobileKpiDailyDetail>(`/parent-accounts/me/operations/mobile-kpis/days/${tradeDate}`)

export const getParentMobileKpiDayCsv = (tradeDate: string) =>
  api.get<Blob>(`/parent-accounts/me/operations/mobile-kpis/days/${tradeDate}/csv`, { responseType: 'blob' })

export const rebuildParentMobileKpiDay = (tradeDate: string) =>
  api.post<MobileKpiDailyDetail>(`/parent-accounts/me/operations/mobile-kpis/days/${tradeDate}/rebuild`)

export const getParentMobileKpiWeeks = () =>
  api.get<MobileKpiWeeklyList>('/parent-accounts/me/operations/mobile-kpis/weeks')

export const getParentMobileKpiWeek = (weekStartYmd: string) =>
  api.get<MobileKpiWeeklyDetail>(`/parent-accounts/me/operations/mobile-kpis/weeks/${weekStartYmd}`)

export const getParentMobileKpiWeekCsv = (weekStartYmd: string) =>
  api.get<Blob>(`/parent-accounts/me/operations/mobile-kpis/weeks/${weekStartYmd}/csv`, { responseType: 'blob' })

export const getParentMobileKpiRecipients = () =>
  api.get<MobileKpiRecipients>('/parent-accounts/me/operations/mobile-kpis/recipients')

export const updateParentMobileKpiRecipient = (userId: string, emailMobileKpiReport: boolean) =>
  api.put<MobileKpiRecipients>('/parent-accounts/me/operations/mobile-kpis/recipients', {
    user_id: userId,
    email_mobile_kpi_report: emailMobileKpiReport,
  })

export const getParentMobileWeeklyReportSettings = () =>
  api.get<{ opt_in: boolean; last_sent_at?: string | null }>('/parent-accounts/me/operations/mobile-weekly-report/settings')

export const updateParentMobileWeeklyReportSettings = (optIn: boolean) =>
  api.put<{ opt_in: boolean; last_sent_at?: string | null }>(
    '/parent-accounts/me/operations/mobile-kpis/settings',
    { opt_in: optIn },
  )

export const sendParentMobileWeeklyReportNow = () =>
  api.post<{ opt_in: boolean; last_sent_at?: string | null }>('/parent-accounts/me/operations/mobile-kpis/send-now')


// ── Shop mobile operator bookings ─────────────────────────────────────────────
export type ShopMobileBookingStatus = 'pending' | 'accepted' | 'declined' | 'cancelled' | 'expired' | 'moved_to_pool'
export type ShopMobileVisitLocationType = 'customer_site' | 'at_shop'

export interface ShopMobileOperatorOption {
  tenant_id: string
  tenant_slug: string
  tenant_name: string
  shop_number?: string | null
  plan_code: string
  routing_rule?: string | null
}

export interface ShopMobileBooking {
  id: string
  parent_account_id: string
  requesting_tenant_id: string
  requesting_shop_name: string
  requesting_shop_number?: string | null
  target_operator_tenant_id: string
  target_operator_name: string
  target_operator_shop_number?: string | null
  created_by_user_id: string
  status: ShopMobileBookingStatus
  customer_name: string
  phone?: string | null
  email?: string | null
  vehicle_make?: string | null
  vehicle_model?: string | null
  registration_plate?: string | null
  visit_location_type: ShopMobileVisitLocationType
  job_address: string
  job_suburb?: string | null
  job_state_code?: string | null
  operator_routing_rule?: string | null
  preferred_scheduled_at?: string | null
  job_type?: string | null
  notes?: string | null
  operator_response_at?: string | null
  operator_response_by_user_id?: string | null
  decline_reason?: string | null
  resulting_auto_key_job_id?: string | null
  resulting_job_number?: string | null
  job_status?: string | null
  job_scheduled_at?: string | null
  schedule_conflict_warning?: string | null
  offer_expires_at?: string | null
  pool_intake_job_id?: string | null
  created_at: string | null
}

export interface ShopMobileBookingCreate {
  suburb: string
  state_code: string
  target_operator_tenant_id?: string | null
  customer_name: string
  phone?: string | null
  email?: string | null
  vehicle_make?: string | null
  vehicle_model?: string | null
  registration_plate?: string | null
  visit_location_type?: ShopMobileVisitLocationType
  job_address: string
  preferred_scheduled_at?: string | null
  job_type?: string | null
  notes?: string | null
}

export const listShopMobileOperators = () =>
  api.get<ShopMobileOperatorOption[]>('/shop-mobile-bookings/operators')
export const suggestShopMobileOperator = (suburb: string, state_code: string) =>
  api.get<ShopMobileOperatorOption | null>('/shop-mobile-bookings/suggest-operator', {
    params: { suburb, state_code },
  })
export const createShopMobileBooking = (payload: ShopMobileBookingCreate) =>
  api.post<ShopMobileBooking>('/shop-mobile-bookings', payload)
export const listShopMobileBookings = (status?: ShopMobileBookingStatus) =>
  api.get<{ items: ShopMobileBooking[]; total: number; limit: number; offset: number }>('/shop-mobile-bookings', {
    params: status ? { status } : {},
  })
export const getShopMobileBooking = (id: string) =>
  api.get<ShopMobileBooking>(`/shop-mobile-bookings/${id}`)
export const cancelShopMobileBooking = (id: string) =>
  api.post<ShopMobileBooking>(`/shop-mobile-bookings/${id}/cancel`)
export const acceptShopMobileBooking = (id: string) =>
  api.post<ShopMobileBooking>(`/shop-mobile-bookings/${id}/accept`)
export const declineShopMobileBooking = (id: string, decline_reason?: string) =>
  api.post<ShopMobileBooking>(`/shop-mobile-bookings/${id}/decline`, { decline_reason })

// ── Customers ─────────────────────────────────────────────────────────────────
export interface Customer {
  id: string; tenant_id: string; full_name: string
  email?: string; phone?: string; address?: string; notes?: string; created_at: string | null
}

// ── Customer Accounts (Fleet/B2B) ─────────────────────────────────────────────
export type FleetAccountType = 'Dealership' | 'Rental Fleet' | 'Government Fleet' | 'Corporate Fleet' | 'Car Auctions' | 'Other'
export type FleetBillingCycle = 'Monthly' | 'Fortnightly' | 'Weekly'

export interface CustomerAccount {
  id: string
  tenant_id: string
  name: string
  account_code?: string | null
  contact_name?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  billing_address?: string | null
  payment_terms_days: number
  notes?: string | null
  is_active: boolean
  created_at: string
  customer_ids?: string[]
  // Fleet/Dealer fields
  account_type?: FleetAccountType | null
  fleet_size?: number | null
  primary_contact_name?: string | null
  primary_contact_phone?: string | null
  billing_cycle?: FleetBillingCycle | null
  credit_limit?: number | null
  account_notes?: string | null
}

export interface CustomerAccountCreate {
  name: string
  account_code?: string | null
  contact_name?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  billing_address?: string | null
  payment_terms_days?: number
  notes?: string | null
  // Fleet/Dealer fields
  account_type?: FleetAccountType | null
  fleet_size?: number | null
  primary_contact_name?: string | null
  primary_contact_phone?: string | null
  billing_cycle?: FleetBillingCycle | null
  credit_limit?: number | null
  account_notes?: string | null
}

export const listCustomerAccounts = () => api.get<CustomerAccount[]>('/customer-accounts')
export const createCustomerAccount = (data: CustomerAccountCreate) => api.post<CustomerAccount>('/customer-accounts', data)
export const updateCustomerAccount = (id: string, data: Partial<CustomerAccountCreate>) => api.patch<CustomerAccount>(`/customer-accounts/${id}`, data)
export const listCustomers = (params?: { limit?: number; offset?: number; sort_by?: string; sort_dir?: 'asc' | 'desc'; q?: string }) =>
  api.get<Customer[]>('/customers', { params })
export const getCustomer = (id: string) => api.get<Customer>(`/customers/${id}`)
export const createCustomer = (data: Omit<Customer, 'id' | 'tenant_id' | 'created_at'>) =>
  api.post<Customer>('/customers', data)
export const updateCustomer = (id: string, data: Partial<Omit<Customer, 'id' | 'tenant_id' | 'created_at'>>) =>
  api.patch<Customer>(`/customers/${id}`, data)

// ── Watches ───────────────────────────────────────────────────────────────────
export interface Watch {
  id: string; tenant_id: string; customer_id: string
  brand?: string; model?: string; serial_number?: string | null
  movement_type?: string; condition_notes?: string; created_at: string | null
}
export const listWatches = (customerId?: string) =>
  api.get<Watch[]>('/watches', { params: customerId ? { customer_id: customerId } : {} })
export const getWatch = (id: string) => api.get<Watch>(`/watches/${id}`)
export const createWatch = (data: Omit<Watch, 'id' | 'tenant_id' | 'created_at'>) =>
  api.post<Watch>('/watches', data)
export const updateWatch = (id: string, data: Partial<Pick<Watch, 'brand' | 'model' | 'serial_number' | 'movement_type' | 'condition_notes'>>) =>
  api.patch<Watch>(`/watches/${id}`, data)

// ── Repair Jobs ───────────────────────────────────────────────────────────────
export type JobStatus = 'awaiting_quote' | 'awaiting_go_ahead' | 'go_ahead' | 'no_go' | 'working_on' | 'awaiting_parts' | 'parts_to_order' | 'sent_to_labanda' | 'quoted_by_labanda' | 'at_third_party_for_quoting' | 'third_party_quote_approved' | 'at_third_party_repairer' | 'service' | 'completed' | 'awaiting_collection' | 'collected' | 'awaiting_customer_details' | 'en_route' | 'on_site' | 'booked' | 'pending_booking' | 'quote_sent' | 'awaiting_booking_confirmation' | 'booking_confirmed' | 'booking_on_hold' | 'booking_completed' | 'job_delayed' | 'work_completed' | 'invoice_paid' | 'failed_job'
export interface RepairJob {
  id: string; tenant_id: string; watch_id: string; assigned_user_id?: string; customer_account_id?: string
  job_number: string; status_token: string; title: string; description?: string; priority: string
  status: JobStatus; salesperson?: string; collection_date?: string; deposit_cents: number; pre_quote_cents: number; cost_cents: number
  internal_notes?: string | null
  parts_eta?: string | null
  status_changed_at?: string | null
  created_at: string
  customer_name?: string | null
  customer_phone?: string | null
  customer_email?: string | null
  claimed_by_user_id?: string | null
  claimed_by_name?: string | null
  tracking_sms_sent?: boolean
  tracking_sms_skipped_reason?: 'no_phone' | 'sms_not_configured' | 'send_failed' | null
  custom_fields_json?: string | null
}
export const listJobs = (params?: { limit?: number; offset?: number; sort_by?: string; sort_dir?: 'asc' | 'desc'; status?: string; customer_id?: string; assigned_user_id?: string; q?: string; cost_outlier?: boolean }) =>
  api.get<RepairJob[]>('/repair-jobs', { params })
export const getJob = (id: string) => api.get<RepairJob>(`/repair-jobs/${id}`)
export const deleteJob = (id: string) => api.delete(`/repair-jobs/${id}`)
export interface RepairJobCreatePayload {
  watch_id: string
  assigned_user_id?: string | null
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
  job_number_override?: string
}
export function trackingSmsWarning(reason: RepairJob['tracking_sms_skipped_reason']): string | null {
  if (!reason) return null
  if (reason === 'no_phone') return 'Tracking SMS was not sent — customer has no phone number on file.'
  if (reason === 'sms_not_configured') return 'Tracking SMS was not sent — SMS is not configured for this shop.'
  return 'Tracking SMS could not be sent. Check the job and send the tracking link manually if needed.'
}

export const createJob = (data: RepairJobCreatePayload) =>
  api.post<RepairJob>('/repair-jobs', data)
export const updateJob = (id: string, data: {
  customer_account_id?: string | null
  title?: string
  cost_cents?: number
  pre_quote_cents?: number
  priority?: string
  salesperson?: string
  collection_date?: string
  deposit_cents?: number
  description?: string
  assigned_user_id?: string | null
  clear_assigned_user?: boolean
  internal_notes?: string | null
  parts_eta?: string | null
}) => api.patch<RepairJob>(`/repair-jobs/${id}`, data)
export const updateJobStatus = (id: string, status: JobStatus, note?: string) =>
  api.post(`/repair-jobs/${id}/status`, { status, note })
export const quickStatusAction = updateJobStatus
export const addJobNote = (id: string, note: string) =>
  api.post(`/repair-jobs/${id}/note`, { note })
export const claimJob = (id: string) =>
  api.post<RepairJob>(`/repair-jobs/${id}/claim`)
export const releaseJob = (id: string) =>
  api.post<RepairJob>(`/repair-jobs/${id}/release`)

/** Watch jobs board queue: status-only transition (no SMS/email). */
export const repairJobQueueSwipe = (id: string, direction: 'left' | 'right') =>
  api.post<RepairJob>(`/repair-jobs/${id}/queue-swipe`, { direction })

/** Per-user repair queue progress for the tenant's current shop day (server; tenant timezone). */
export interface RepairQueueDayStateResponse {
  shop_date: string
  mode: string
  done_ids: string[]
  queue_order_ids?: string[]
  stats: { advanced?: number; checkedIn?: number; skipped?: number }
}

export const getRepairQueueDayState = (mode: 'watch' | 'shoe') =>
  api.get<RepairQueueDayStateResponse>('/me/repair-queue-day', { params: { mode } })

export const putRepairQueueDayState = (
  mode: 'watch' | 'shoe',
  body: {
    done_ids: string[]
    queue_order_ids?: string[]
    stats: { advanced: number; checkedIn: number; skipped: number }
  },
) => api.put<RepairQueueDayStateResponse>('/me/repair-queue-day', { mode, ...body })

export const deleteRepairQueueDayState = (mode: 'watch' | 'shoe') =>
  api.delete('/me/repair-queue-day', { params: { mode } })


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
  item_type: 'labor' | 'part' | 'fee' | 'discount'; description: string
  quantity: number; unit_price_cents: number
}
export interface Quote {
  id: string; tenant_id: string; repair_job_id: string; status: QuoteStatus
  subtotal_cents: number; tax_cents: number; gst_enabled: boolean; gst_inclusive: boolean
  total_cents: number; currency: string
  approval_token: string; sent_at?: string; created_at: string
  customer_name?: string | null
  job_number?: string | null
}
export const listQuotes = (repairJobId?: string, params?: { limit?: number; offset?: number; sort_by?: string; sort_dir?: 'asc' | 'desc' }) =>
  api.get<Quote[]>('/quotes', { params: { ...(repairJobId ? { repair_job_id: repairJobId } : {}), ...params } })
export const createQuote = (data: { repair_job_id: string; gst_enabled: boolean; gst_inclusive: boolean; line_items: QuoteLineItemInput[] }) =>
  api.post<Quote>('/quotes', data)
export const sendQuote = (id: string) => api.post<{ id: string; status: string; sent_at: string; approval_token: string }>(`/quotes/${id}/send`)
export const resendQuote = (id: string) => api.post<{ id: string; status: string; sent_at: string; approval_token: string }>(`/quotes/${id}/resend`)
export const createInvoiceFromQuote = (quoteId: string) =>
  api.post<{ invoice: { id: string; invoice_number: string; total_cents: number; status: string } }>(`/invoices/from-quote/${quoteId}`)
export const getQuoteLineItems = (quoteId: string) => api.get<Array<QuoteLineItemInput & { id: string; total_price_cents: number }>>(`/quotes/${quoteId}/line-items`)

// Public (no auth)
export const getPublicQuote = (token: string) =>
  axios.get<{ shop_name?: string | null; shop_phone?: string | null; id: string; status: string; subtotal_cents: number; tax_cents: number; gst_enabled: boolean; gst_inclusive: boolean; total_cents: number; currency: string; sent_at?: string; approval_token_expires_at?: string; line_items: Array<{ item_type: string; description: string; quantity: number; unit_price_cents: number; total_price_cents: number }> }>(withApiOrigin(`/v1/public/quotes/${token}`))
export const submitQuoteDecision = (token: string, decision: 'approved' | 'declined', signature?: string | null) =>
  axios.post(withApiOrigin(`/v1/public/quotes/${token}/decision`), { decision, signature })

export interface PublicJobStatus {
  job_number: string
  status: string
  title: string
  priority: string
  pre_quote_cents: number
  created_at: string
  collection_date?: string | null
  shop?: { name?: string | null; phone?: string | null; email?: string | null }
  watch: {
    brand?: string
    model?: string
    serial_number?: string
  }
  history: Array<{
    old_status?: string
    new_status: string
    created_at: string
  }>
}
export const getPublicJobStatus = (token: string) =>
  axios.get<PublicJobStatus>(withApiOrigin(`/v1/public/jobs/${token}`))

export const getPublicJobQrUrl = (token: string) =>
  withApiOrigin(`/v1/public/jobs/${token}/qr`)

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
  history: Array<{
    old_status: string | null
    new_status: string
    change_note?: string | null
    created_at: string
  }>
}

export const getPublicShoeJobStatus = (token: string) =>
  axios.get<PublicShoeJobStatus>(withApiOrigin(`/v1/public/shoe-jobs/${token}`))

export interface CustomerPortalPendingAction {
  kind:
    | 'watch_quote_decision'
    | 'shoe_quote_decision'
    | 'auto_key_quote_decision'
    | 'auto_key_booking_confirm'
    | 'auto_key_invoice_checkout'
    | 'job_receipt'
    | 'auto_key_invoice_receipt'
  token: string
  url: string
  label?: string
}

export interface CustomerPortalJob {
  id: string
  /** Backend declares this `str`; these are the values it emits today. */
  type: 'watch' | 'shoe' | 'auto_key' | (string & {})
  job_number: string
  title: string
  status: string
  created_at: string
  status_token: string
  status_url: string
  detail?: string | null
  pending_actions?: CustomerPortalPendingAction[]
}

export interface CustomerPortalShop {
  tenant_id: string
  shop_name: string
  logo_url?: string | null
  brand_color?: string | null
  shop_phone?: string | null
  shop_email?: string | null
  jobs?: CustomerPortalJob[]
}

export interface CustomerPortalLookupResponse {
  email?: string | null
  shops?: CustomerPortalShop[]
  status_notify_email?: boolean | null
  status_notify_sms?: boolean | null
}

export const customerPortalLookup = (email: string, includeHistory = false) =>
  axios.post<CustomerPortalLookupResponse>(
    withApiOrigin('/v1/public/customer-lookup'),
    { email, include_history: includeHistory },
    includeHistory ? { params: { include_history: true } } : undefined,
  )

// ── Stocktake ────────────────────────────────────────────────────────────────
export interface StockItem {
  id: string
  tenant_id: string
  item_code: string
  group_code: string
  group_name?: string | null
  item_description?: string | null
  description2?: string | null
  description3?: string | null
  full_description?: string | null
  unit_description?: string | null
  pack_description?: string | null
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
  sources?: Record<string, number>
  sheet_names?: string[]
}

export interface StocktakeProgress {
  counted_items?: number
  total_items?: number
}

export type StocktakeStatus = 'draft' | 'in_progress' | 'completed' | 'approved'

export interface StocktakeSession {
  id: string
  tenant_id: string
  name: string
  status: StocktakeStatus
  created_by_user_id?: string | null
  completed_by_user_id?: string | null
  group_code_filter?: string | null
  group_name_filter?: string | null
  search_filter?: string | null
  notes?: string | null
  created_at: string
  completed_at?: string | null
  progress?: StocktakeProgress
}

export interface StocktakeLine {
  id: string
  stocktake_session_id: string
  stock_item_id: string
  expected_qty: number
  counted_qty?: number | null
  variance_qty?: number | null
  variance_value_cents?: number | null
  counted_by_user_id?: string | null
  counted_at?: string | null
  notes?: string | null
  item_code: string
  group_code: string
  group_name?: string | null
  item_description?: string | null
  full_description?: string | null
  system_stock_qty: number
  cost_price_cents: number
  retail_price_cents: number
}

export interface StocktakeSessionDetail extends StocktakeSession {
  lines?: StocktakeLine[]
}

export interface StocktakeGroupSummary {
  group_code: string
  group_name?: string | null
  item_count?: number
  counted_count?: number
  variance_count?: number
  total_variance_qty?: number
  total_variance_value_cents?: number
}

export interface StocktakeReport {
  session: StocktakeSession
  matched_item_count?: number
  missing_item_count?: number
  over_count_item_count?: number
  total_variance_qty?: number
  total_variance_value_cents?: number
  groups?: StocktakeGroupSummary[]
}

export const importStockFile = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post<StockImportSummaryResponse>('/stock/import', formData)
}

export const listStockItems = (params?: {
  search?: string
  group_code?: string
  group_name?: string
  hide_zero_stock?: boolean
  limit?: number
  offset?: number
}) =>
  api.get<{ items: StockItem[]; total: number; limit: number; offset: number }>('/stock/items', { params })

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
  withApiOrigin(`/v1/public/shoe-jobs/${token}/qr`)

// ── Work Logs ─────────────────────────────────────────────────────────────────
export interface WorkLog {
  id: string; tenant_id: string; repair_job_id: string; user_id?: string
  note?: string; minutes_spent: number; started_at?: string; ended_at?: string; created_at: string | null
}
export const listWorkLogs = (repairJobId: string) =>
  api.get<WorkLog[]>('/work-logs', { params: { repair_job_id: repairJobId } })
export const createWorkLog = (data: { repair_job_id: string; note?: string; minutes_spent?: number }) =>
  api.post<WorkLog>('/work-logs', data)

// ── Attachments ───────────────────────────────────────────────────────────────
export interface Attachment {
  id: string; tenant_id: string; repair_job_id?: string; watch_id?: string
  shoe_repair_job_id?: string | null
  auto_key_job_id?: string | null
  storage_key: string; file_name?: string; content_type?: string; file_size_bytes?: number
  label?: string; created_at: string | null
}
export interface AttachmentDownloadLinkResponse {
  download_url: string
  expires_in_seconds: number
}
export const API_ROUTES = {
  attachmentDownload: (storageKey: string) => withApiOrigin(`/v1/attachments/download/${encodeURIComponent(storageKey)}`),
  attachmentDownloadLink: (storageKey: string) => `/attachments/download-link/${encodeURIComponent(storageKey)}`,
  publicAutoKeyInvoice: (token: string) => withApiOrigin(`/v1/public/auto-key-invoice/${token}`),
  publicAutoKeyInvoiceCheckout: (token: string) => withApiOrigin(`/v1/public/auto-key-invoice/${token}/checkout`),
  publicAutoKeyBooking: (token: string) => withApiOrigin(`/v1/public/auto-key-booking/${token}`),
  publicAutoKeyBookingConfirm: (token: string) => withApiOrigin(`/v1/public/auto-key-booking/${token}/confirm`),
} as const
export const listAttachments = (repairJobId: string, params?: { limit?: number; offset?: number; sort_by?: string; sort_dir?: 'asc' | 'desc' }) =>
  api.get<Attachment[]>('/attachments', { params: { repair_job_id: repairJobId, ...params } })
export const uploadAttachment = (file: File, repairJobId: string, label?: string) => {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams({ repair_job_id: repairJobId })
  if (label) params.append('label', label)
  return api.post<Attachment>(`/attachments?${params.toString()}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}
export const listShoeAttachments = (shoeRepairJobId: string) =>
  api.get<Attachment[]>('/attachments', { params: { shoe_repair_job_id: shoeRepairJobId } })
export const uploadShoeAttachment = (file: File, shoeRepairJobId: string, label?: string) => {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams({ shoe_repair_job_id: shoeRepairJobId })
  if (label) params.append('label', label)
  return api.post<Attachment>(`/attachments?${params.toString()}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}
export const getAttachmentDownloadUrl = (storageKey: string) => {
  return API_ROUTES.attachmentDownload(storageKey)
}

/** Downloads an attachment using Authorization header (no token in URL). */
export async function downloadAttachment(storageKey: string, fileName?: string): Promise<void> {
  const response = await api.get<Blob>(`/attachments/download/${encodeURIComponent(storageKey)}`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(response.data)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName || storageKey
  a.click()
  URL.revokeObjectURL(url)
}

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
  tax_cents: number; gst_enabled: boolean; gst_inclusive: boolean
  total_cents: number; currency: string; created_at: string
  customer_name?: string | null
  xero_invoice_id?: string | null
  xero_sync_status?: string | null
  xero_sync_error?: string | null
  xero_synced_at?: string | null
  xero_online_invoice_url?: string | null
  invoice?: Invoice
}
export const listInvoices = (params?: { limit?: number; offset?: number }) =>
  api.get<{ items: Invoice[]; total: number; limit: number; offset: number }>(
    '/invoices',
    params && Object.keys(params).length ? { params } : undefined,
  )
export const getInvoice = (id: string) => api.get<Invoice>(`/invoices/${id}`)
export const getInvoiceLineItems = (invoiceId: string) =>
  api.get<Array<{ id: string; item_type: string; description: string; quantity: number; unit_price_cents: number; total_price_cents: number }>>(`/invoices/${invoiceId}/line-items`)
export const recordPayment = (invoiceId: string, amount_cents: number) =>
  api.post(`/invoices/${invoiceId}/payments`, { amount_cents })
export const sendWatchInvoice = (invoiceId: string) =>
  api.post<{ invoice_id: string; email_sent: boolean; email_skipped_reason?: string | null }>(
    `/invoices/${invoiceId}/send`,
  )
export const retryInvoiceXeroSync = (invoiceId: string) =>
  api.post<Invoice>(`/invoices/${invoiceId}/xero/retry`)

// ── CSV Import ────────────────────────────────────────────────────────────────
export interface CsvImportResult {
  import_id: string
  imported: number; skipped: number; customers_created: number; total_rows: number
  skipped_reasons: Record<string, number>
  dry_run?: boolean
  source_sheet?: string | null
  duplicate_customer_rows_in_file?: number
  /** watch | shoe | mobile — which module received the import */
  import_target?: string | null
}
export type CsvImportTarget = 'watch' | 'shoe' | 'mobile'

export const importCsv = (file: File, options?: {
  replaceExisting?: boolean
  clearTabs?: string[]
  dryRun?: boolean
  sheetName?: string
  importTarget?: CsvImportTarget
}) => {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams()
  if (options?.replaceExisting) params.append('replace_existing', 'true')
  if (options?.dryRun) params.append('dry_run', 'true')
  if (options?.sheetName) params.append('sheet_name', options.sheetName)
  if (options?.clearTabs?.length) params.append('clear_tabs', options.clearTabs.join(','))
  if (options?.importTarget) params.append('import_target', options.importTarget)
  const qs = params.toString() ? `?${params.toString()}` : ''
  return api.post<CsvImportResult>(`/import/csv${qs}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000, // 10 min for large imports
  })
}

// ── Reports ───────────────────────────────────────────────────────────────────
export interface ReportsSummary {
  counts: {
    jobs: number; customers: number; watches: number; quotes: number; invoices: number
    shoe_jobs?: number
  }
  jobs_by_status: Record<string, number>
  shoe_jobs_by_status?: Record<string, number>
  shoe_quotes?: {
    by_status: Record<string, number>
    approval_rate_percent: number
  }
  quotes_by_status: Record<string, number>
  sales_funnel: {
    approved_quotes: number; sent_quotes: number; declined_quotes: number; approval_rate_percent: number
  }
  financials: {
    billed_cents: number
    revenue_cents: number
    cost_cents: number
    cost_outlier_jobs?: number
    cost_outlier_watch_jobs?: number
    cost_outlier_shoe_jobs?: number
    outstanding_cents: number
    gross_profit_cents: number
    gross_margin_percent: number
    /** Total value of void/refunded invoices — excluded from billed/revenue, shown for transparency. */
    voided_cents: number
  }
  operations: {
    work_minutes: number
    avg_revenue_per_job_cents: number
    avg_turnaround_days: number | null
    quote_to_invoice_pct: number
    avg_quote_response_hours: number | null
  }
  by_category?: {
    watch: SalesCategorySummary
    shoe: SalesCategorySummary
    mobile: SalesCategorySummary
  }
}
export interface SalesCategorySummary {
  jobs: number
  billed_cents: number
  revenue_cents: number
  cost_cents: number
  outstanding_cents: number
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
  mobile_commission_rules_json?: string | null
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

export interface ReportsTechBreakdownEntry {
  user_id: string
  user_name: string
  total_minutes: number
  jobs_count: number
}
export const getReportsTechBreakdown = () =>
  api.get<ReportsTechBreakdownEntry[]>('/reports/tech-breakdown')

export interface ReportsWidgets {
  overdue_jobs_count: number
  quotes_pending_7d_count: number
  overdue_invoices_count: number
  overdue_collection_count: number
}
export const getReportsWidgets = () => api.get<ReportsWidgets>('/reports/widgets')

// Export CSV (returns blob)
export const getExportJobsCsv = () => api.get<Blob>('/reports/export/jobs', { responseType: 'blob' })
export const getExportCustomersCsv = () => api.get<Blob>('/reports/export/customers', { responseType: 'blob' })
export const getExportInvoicesCsv = () => api.get<Blob>('/reports/export/invoices', { responseType: 'blob' })

export type ReportPeriod = 'day' | 'week' | 'month' | 'quarter'

export type SalesCategory = 'watch' | 'shoe' | 'mobile' | 'all'
export interface SalesExportDateFilter {
  /** Calendar-period shortcut; overrides date_from/date_to when set. */
  period?: ReportPeriod
  /** Civil date YYYY-MM-DD within the period (default: today); used with `period`. */
  reference_date?: string
  /** Civil date YYYY-MM-DD, inclusive. Ignored if `period` is set. */
  date_from?: string
  /** Civil date YYYY-MM-DD, inclusive. Ignored if `period` is set. */
  date_to?: string
}
export const getExportSalesCsv = (category: SalesCategory, filter?: SalesExportDateFilter) =>
  api.get<Blob>('/reports/export/sales', { params: { category, ...filter }, responseType: 'blob' })

/** Sales-by-category summary for a date range — mirrors the rows /export/sales would return. */
export const getCategorySummary = (filter?: SalesExportDateFilter) =>
  api.get<{ watch: SalesCategorySummary; shoe: SalesCategorySummary; mobile: SalesCategorySummary }>(
    '/reports/category-summary',
    { params: filter },
  )

export interface GstCategorySummary {
  invoice_count: number
  subtotal_cents: number
  gst_cents: number
  total_cents: number
}
export interface GstSummary {
  watch: GstCategorySummary
  mobile: GstCategorySummary
  combined: GstCategorySummary
}
/** GST collected on paid watch + mobile invoices for a date range (shoe repairs have no GST tracking). */
export const getGstSummary = (filter?: SalesExportDateFilter) =>
  api.get<GstSummary>('/reports/gst-summary', { params: filter })

export interface PeriodReportSummary {
  period: ReportPeriod
  reference_date: string
  period_start: string
  period_end: string
  jobs_opened: number
  watch_jobs_opened: number
  shoe_jobs_opened: number
  auto_key_jobs_opened: number
  customers_new: number
  financials: {
    billed_cents: number
    revenue_cents: number
    cost_cents: number
    gross_profit_cents: number
    gross_margin_percent: number
  }
  sales_funnel: {
    quotes_sent: number
    quotes_approved: number
    quotes_declined: number
    approval_rate_percent: number
  }
  operations: {
    work_minutes: number
    avg_revenue_per_job_cents: number
  }
}

export const getPeriodReportSummary = (params: { period: ReportPeriod; reference_date?: string }) =>
  api.get<PeriodReportSummary>('/reports/period-summary', { params })

export const getExportPeriodSummaryCsv = (params: { period: ReportPeriod; reference_date?: string }) =>
  api.get<Blob>('/reports/export/period-summary', { params, responseType: 'blob' })

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
  stripe_connect_account_present?: boolean
  stripe_connect_charges_enabled?: boolean
  xero_configured?: boolean
  xero_connected?: boolean
  xero_connection_status?: string | null
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
  mobile_commission_rules_json?: string | null
}) => api.post<TenantUser>('/users', data)

export const updateUser = (
  userId: string,
  data: {
    full_name?: string
    role?: 'owner' | 'manager' | 'tech' | 'intake'
    password?: string
    is_active?: boolean
    mobile_commission_rules_json?: string | null
  },
) => api.patch<TenantUser>(`/users/${userId}`, data)

export interface PlatformUser extends TenantUser {
  tenant_slug: string
  tenant_name: string
}

export const listPlatformUsers = () => api.get<PlatformUser[]>('/platform-admin/users')

export interface PlatformTenant {
  id: string
  slug: string
  name: string
  plan_code: string
  is_active: boolean
  signup_payment_pending: boolean
  billing_exempt?: boolean
  subscription_status?: string | null
  user_count: number
  created_at: string
}

export interface PlatformEnterShopResponse {
  access_token: string
  refresh_token: string
  expires_in_seconds: number
  refresh_expires_in_seconds: number
  tenant_id: string
  tenant_name: string
}

export const listPlatformTenants = () => api.get<PlatformTenant[]>('/platform-admin/tenants')
export interface PlatformReportTenantRow {
  tenant_id: string
  tenant_name: string
  tenant_slug: string
  plan_code: string
  is_active: boolean
  users: number
  active_users: number
  repair_jobs: number
  shoe_jobs: number
  auto_key_jobs: number
  jobs_total: number
  jobs_last_30_days: number
  invoices: number
  paid_invoices: number
  invoices_last_30_days: number
  billed_total_cents: number
  paid_total_cents: number
  last_activity_at?: string
  logins_last_7_days: number
  days_since_activity?: number | null
  health_status: 'healthy' | 'attention' | 'suspended'
}
export interface PlatformReportsResponse {
  generated_at: string
  totals: {
    tenants: number
    users: number
    active_users: number
    repair_jobs: number
    shoe_jobs: number
    auto_key_jobs: number
    invoices: number
    paid_invoices: number
    billed_total_cents: number
    paid_total_cents: number
    jobs_last_30_days: number
    invoices_last_30_days: number
    health: {
      active_tenants: number
      suspended_tenants: number
      tenants_no_activity_7_days: number
      tenants_no_jobs_30_days: number
      tenants_no_active_users: number
    }
  }
  tenants: PlatformReportTenantRow[]
}
export const getPlatformReports = () => api.get<PlatformReportsResponse>('/platform-admin/reports')
export interface PlatformActivityEvent {
  id: string
  tenant_id: string
  actor_user_id?: string
  actor_email?: string
  entity_type: string
  entity_id?: string
  event_type: string
  event_summary: string
  created_at: string
}
export const listPlatformActivity = (limit = 100, offset = 0) =>
  api.get<PlatformActivityEvent[]>('/platform-admin/activity', { params: { limit, offset } })
export const platformAdminEnterShop = (tenantId: string) =>
  api.post<PlatformEnterShopResponse>(`/platform-admin/enter-shop/${tenantId}`)
export const setPlatformTenantStatus = (tenantId: string, is_active: boolean, reason?: string) =>
  api.patch<PlatformTenant>(`/platform-admin/tenants/${tenantId}/status`, { is_active, reason })
export const forcePlatformTenantLogout = (tenantId: string, reason?: string) =>
  api.post<{ ok: boolean; tenant_id: string; auth_revoked_at: string }>(`/platform-admin/tenants/${tenantId}/force-logout`, { reason })
export const deletePlatformTenant = (tenantId: string) =>
  api.delete(`/platform-admin/tenants/${tenantId}`)
export const setPlatformTenantPlan = (tenantId: string, plan_code: string, reason?: string) =>
  api.patch<PlatformTenant>(`/platform-admin/tenants/${tenantId}/plan`, { plan_code, reason })
export const markPlatformTenantPaid = (tenantId: string) =>
  api.post<PlatformTenant>(`/platform-admin/tenants/${tenantId}/mark-paid`)
export const setPlatformTenantBillingExempt = (
  tenantId: string,
  billing_exempt: boolean,
  reason?: string,
  cancel_stripe_subscription = true,
) =>
  api.post<PlatformTenant>(`/platform-admin/tenants/${tenantId}/billing-exempt`, {
    billing_exempt,
    reason,
    cancel_stripe_subscription,
  })
export const updatePlatformTenant = (tenantId: string, payload: { name?: string; slug?: string; owner_email?: string; new_password?: string }) =>
  api.patch<PlatformTenant>(`/platform-admin/tenants/${tenantId}`, payload)

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
  applicable_shoe_types?: string[]
  complexity?: string
  estimated_days_min?: number
  estimated_days_max?: number
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
  shoe_type?: string | null
  brand?: string | null
  color?: string | null
  description_notes?: string | null
  created_at: string
}

export const listShoes = (customerId?: string) =>
  api.get<Shoe[]>('/shoe-repair-jobs/shoes', customerId ? { params: { customer_id: customerId } } : undefined)

// ── Auto Key Jobs ────────────────────────────────────────────────────────────
export type AutoKeyProgrammingStatus = 'pending' | 'in_progress' | 'programmed' | 'failed' | 'not_required'

export interface AutoKeyJob {
  id: string
  tenant_id: string
  customer_id: string
  assigned_user_id?: string | null
  customer_account_id?: string | null
  job_number: string
  status_token: string
  title: string
  description?: string | null
  vehicle_make?: string | null
  vehicle_model?: string | null
  vehicle_year?: number | null
  registration_plate?: string | null
  vin?: string | null
  key_type?: string | null
  key_quantity: number
  programming_status: AutoKeyProgrammingStatus
  priority: 'low' | 'normal' | 'high' | 'urgent'
  status: JobStatus
  salesperson?: string | null
  collection_date?: string | null
  deposit_cents: number
  cost_cents: number
  created_at: string | null
  blade_code?: string | null
  chip_type?: string | null
  tech_notes?: string | null
  scheduled_at?: string | null
  job_address?: string | null
  job_type?: string | null
  visit_order?: number | null
  additional_services_json?: string | null
  commission_lead_source?: string
  shop_mobile_booking_request_id?: string | null
  customer_name?: string | null
  customer_phone?: string | null
  pricing_ref_id?: string | null
  /** Backend declares this `str | null`; these are the values it writes today. */
  pricing_type?: 'oem_key' | 'service' | 'garage' | (string & {}) | null
  quoted_price?: number | null
  callout_inclusive?: boolean | null
  custom_fields_json?: string | null
}

export type MobileServicesPricingType = 'oem_key' | 'service' | 'garage'

export interface OemKeyPricingRow {
  id: string
  make: string
  model_variant?: string | null
  job_type: string
  key_type?: string | null
  service_location?: string | null
  tool_required?: string | null
  retail_price?: number | null
  is_poa: boolean
  callout_inclusive: boolean
  notes?: string | null
}

export interface ServicePricingRow {
  id: string
  category: string
  service_name: string
  unit?: string | null
  retail_price?: number | null
  is_poa: boolean
  callout_inclusive: boolean
  notes?: string | null
}

export interface GarageServicingPricingRow {
  id: string
  service_name: string
  description?: string | null
  part_cost_notes?: string | null
  labour_time?: string | null
  retail_price: number
  callout_inclusive: boolean
  notes?: string | null
}

export interface MobileServicesPricingSelection {
  pricing_ref_id: string
  pricing_type: MobileServicesPricingType
  quoted_price: number
  callout_inclusive: boolean
  label?: string
}

export const listMobileServicesOemMakes = () =>
  api.get<string[]>('/mobile-services-pricing/oem-makes')
export const listMobileServicesOemKeyPricing = (make: string) =>
  api.get<OemKeyPricingRow[]>('/mobile-services-pricing/oem-keys', { params: { make } })
export const listMobileServicesServicePricing = () =>
  api.get<ServicePricingRow[]>('/mobile-services-pricing/services')
export const listGarageServicingPricing = () =>
  api.get<GarageServicingPricingRow[]>('/mobile-services-pricing/garage')

export type MobileCatalogueCategory = 'vehicle_key' | 'general_service' | 'garage_door'
export type MobileServicesPricingMeta = {
  oem_row_count: number
  oem_make_count: number
  service_row_count: number
  garage_row_count: number
  /** Catalogue categories this shop sells (owner setting; see /toolkit/mobile-catalogue). */
  enabled_categories: MobileCatalogueCategory[]
}
export const getMobileServicesPricingMeta = () =>
  api.get<MobileServicesPricingMeta>('/mobile-services-pricing/meta')

export interface AutoKeyJobCreatePayload {
  customer_id: string
  customer_account_id?: string
  title: string
  description?: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number
  registration_plate?: string
  vin?: string
  key_type?: string | null
  key_quantity: number
  programming_status: AutoKeyProgrammingStatus
  priority: 'low' | 'normal' | 'high' | 'urgent'
  status: JobStatus
  salesperson?: string
  collection_date?: string
  deposit_cents: number
  cost_cents: number
  assigned_user_id?: string | null
  apply_suggested_quote?: boolean
  send_booking_sms?: boolean
  additional_services?: Array<{ preset?: string; custom?: string }>
  blade_code?: string | null
  chip_type?: string | null
  tech_notes?: string | null
  scheduled_at?: string | null
  job_address?: string | null
  job_type?: string | null
  commission_lead_source?: string | null
  pricing_ref_id?: string | null
  pricing_type?: MobileServicesPricingType | null
  quoted_price?: number | null
  callout_inclusive?: boolean | null
}

export const AUTO_KEY_JOBS_PAGE_SIZE = 500
const AUTO_KEY_JOBS_MAX_PAGES = 40

export type ListAutoKeyJobsParams = {
  customer_id?: string
  status?: string
  assigned_user_id?: string | null
  date_from?: string
  date_to?: string
  include_unscheduled?: boolean
  active_only?: boolean
  limit?: number
  skip?: number
}

export async function listAutoKeyJobs(params?: ListAutoKeyJobsParams) {
  const pageExplicit = params?.limit != null || params?.skip != null
  if (pageExplicit) {
    return api.get<AutoKeyJob[]>('/auto-key-jobs', { params })
  }
  const all: AutoKeyJob[] = []
  let skip = 0
  let total = Number.POSITIVE_INFINITY
  let last = await api.get<AutoKeyJob[]>('/auto-key-jobs', {
    params: { ...params, skip: 0, limit: AUTO_KEY_JOBS_PAGE_SIZE },
  })
  for (let page = 0; page < AUTO_KEY_JOBS_MAX_PAGES; page += 1) {
    const rows = last.data ?? []
    const headerTotal = Number(last.headers['x-total-count'])
    if (Number.isFinite(headerTotal)) total = headerTotal
    all.push(...rows)
    if (rows.length < AUTO_KEY_JOBS_PAGE_SIZE || all.length >= total) {
      last.data = all
      return last
    }
    skip += AUTO_KEY_JOBS_PAGE_SIZE
    last = await api.get<AutoKeyJob[]>('/auto-key-jobs', {
      params: { ...params, skip, limit: AUTO_KEY_JOBS_PAGE_SIZE },
    })
  }
  last.data = all
  return last
}

export interface AutoKeyJobPage {
  items: AutoKeyJob[]
  total: number
  limit: number
  offset: number
}
export const pageAutoKeyJobs = (params: {
  q?: string
  directory?: 'active' | 'completed' | 'all'
  status?: string
  /** Reporting category from the shared vocabulary (pipeline, booking, field, completed, paid, lost). */
  category?: MobileStatusCategoryKey
  /** Cockpit focus (late, unscheduled, …) — applies the exact filter the cockpit tile counted. */
  focus?: MobileCockpitFocusKey
  /** Finance drill-down: rows whose `date_field` falls in the shop-local date range. */
  date_field?: MobileFinanceDateField
  date_from?: string
  date_to?: string
  assigned_user_id?: string
  limit?: number
  offset?: number
}) => api.get<AutoKeyJobPage>('/auto-key-jobs/page', { params })
export const getAutoKeyJob = (id: string) => api.get<AutoKeyJob>(`/auto-key-jobs/${id}`)
export const listAutoKeyJobActivity = (id: string, limit = 100) =>
  api.get<TenantActivityEvent[]>(`/auto-key-jobs/${id}/activity`, { params: { limit } })
export const createAutoKeyJob = (data: AutoKeyJobCreatePayload) => api.post<AutoKeyJob>('/auto-key-jobs', data)
export interface AutoKeyJobUpdatePayload extends Omit<Partial<AutoKeyJobCreatePayload>, 'customer_account_id'> {
  customer_account_id?: string | null
  visit_order?: number | null
}
export const updateAutoKeyJob = (id: string, data: AutoKeyJobUpdatePayload) =>
  api.patch<AutoKeyJob>(`/auto-key-jobs/${id}`, data)
export interface AutoKeyJobStatusUpdateResult extends AutoKeyJob {
  /** True when this status change auto-created an invoice. */
  invoice_created?: boolean
  /** Machine code for why no invoice was created (e.g. "already_invoiced"), or null. */
  invoice_skip_reason?: string | null
}
export const updateAutoKeyJobStatus = (id: string, status: JobStatus, note?: string) =>
  api.post<AutoKeyJobStatusUpdateResult>(`/auto-key-jobs/${id}/status`, { status, note })
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
  gst_enabled: boolean
  gst_inclusive: boolean
  total_cents: number
  currency: string
  sent_at?: string | null
  signed_at?: string | null
  signer_name?: string | null
  has_signature?: boolean
  created_at: string
  line_items?: AutoKeyQuoteLineItem[]
}

export async function resolveQuoteSignatureUrl(quoteId: string): Promise<string> {
  const res = await api.get(`/auto-key-jobs/quotes/${quoteId}/signature`, { responseType: 'blob' })
  return URL.createObjectURL(res.data)
}

export interface AutoKeyInvoice {
  id: string
  tenant_id: string
  auto_key_job_id: string
  auto_key_quote_id?: string | null
  invoice_number: string
  status: string
  subtotal_cents: number
  tax_cents: number
  gst_enabled: boolean
  gst_inclusive: boolean
  total_cents: number
  currency: string
  created_at: string
  payment_method?: string | null
  xero_invoice_id?: string | null
  xero_sync_status?: string | null
  xero_sync_error?: string | null
  xero_synced_at?: string | null
  customer_name?: string | null
  job_number?: string | null
}

export interface AutoKeyQuoteCreatePayload {
  line_items: Array<{
    description: string
    quantity: number
    unit_price_cents: number
  }>
  gst_enabled: boolean
  gst_inclusive: boolean
}

export const listAutoKeyQuotes = (jobId: string) => api.get<AutoKeyQuote[]>(`/auto-key-jobs/${jobId}/quotes`)
export const createAutoKeyQuote = (jobId: string, payload: AutoKeyQuoteCreatePayload) =>
  api.post<AutoKeyQuote>(`/auto-key-jobs/${jobId}/quotes`, payload)
export interface AutoKeySendNotificationResult {
  email_sent: boolean
  email_skipped_reason?: string | null
  email_error_detail?: string | null
  sms_sent?: boolean
  sms_skipped_reason?: string | null
}

export type InvoiceSendChannel = 'sms' | 'email' | 'both'

export const sendAutoKeyQuote = (quoteId: string) =>
  api.post<AutoKeySendNotificationResult & { quote: AutoKeyQuote }>(
    `/auto-key-jobs/quotes/${quoteId}/send`,
  )
export const listAutoKeyInvoices = (jobId: string) => api.get<AutoKeyInvoice[]>(`/auto-key-jobs/${jobId}/invoices`)
export const listAllAutoKeyInvoices = (params?: { limit?: number; offset?: number }) =>
  api.get<AutoKeyInvoice[]>(
    '/auto-key-jobs/invoices',
    params && Object.keys(params).length ? { params } : undefined,
  )
export const createAutoKeyInvoiceFromQuote = (jobId: string, quoteId: string) =>
  api.post<AutoKeyInvoice>(`/auto-key-jobs/${jobId}/invoices/from-quote/${quoteId}`)
export const sendAutoKeyInvoice = (invoiceId: string, channel: InvoiceSendChannel = 'both') =>
  api.post<AutoKeySendNotificationResult & { invoice: AutoKeyInvoice }>(
    `/auto-key-jobs/invoices/${invoiceId}/send`,
    null,
    { params: { channel } },
  )

export const createShoe = (data: Omit<Shoe, 'id' | 'tenant_id' | 'created_at'>) =>
  api.post<Shoe>('/shoe-repair-jobs/shoes', data)
export const updateShoe = (id: string, data: Partial<Pick<Shoe, 'shoe_type' | 'brand' | 'color' | 'description_notes'>>) =>
  api.patch<Shoe>(`/shoe-repair-jobs/shoes/${id}`, data)

// ── Shoe Repair Jobs ──────────────────────────────────────────────────────────
export interface ShoeRepairJobItem {
  id: string
  shoe_repair_job_id: string
  catalogue_key: string
  catalogue_group: string
  item_name: string
  pricing_type: ShoePricingType
  unit_price_cents?: number | null
  quantity: number
  notes?: string | null
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
  shoe?: Shoe | null
  sort_order: number
}

export interface ShoeRepairJob {
  id: string
  tenant_id: string
  shoe_id: string
  customer_account_id?: string | null
  claimed_by_user_id?: string | null
  claimed_by_name?: string | null
  shoe?: Shoe | null
  extra_shoes?: ShoeRepairJobShoe[]
  assigned_user_id?: string | null
  job_number: string
  status_token: string
  title: string
  description?: string | null
  priority: string
  status: string
  salesperson?: string | null
  collection_date?: string | null
  deposit_cents: number
  cost_cents: number
  quote_approval_token: string
  quote_approval_token_expires_at?: string | null
  quote_status: string
  created_at: string
  estimated_ready_by?: string | null
  complexity?: string | null
  estimated_days_min?: number | null
  estimated_days_max?: number | null
  items?: ShoeRepairJobItem[]
  tracking_sms_sent?: boolean
  tracking_sms_skipped_reason?: 'no_phone' | 'sms_not_configured' | 'send_failed' | null
  custom_fields_json?: string | null
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

export const listShoeRepairJobs = (params?: { status?: string; customer_id?: string; cost_outlier?: boolean; limit?: number }) =>
  api.get<ShoeRepairJob[]>('/shoe-repair-jobs', params && Object.keys(params).length ? { params } : undefined)

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
export const addShoeJobNote = (id: string, note: string) =>
  api.post(`/shoe-repair-jobs/${id}/note`, { note })
export interface ShoeJobHistoryEntry {
  id: string; shoe_repair_job_id: string; old_status?: string; new_status: string
  changed_by_user_id?: string; change_note?: string; created_at: string
}
export const getShoeJobHistory = (jobId: string) =>
  api.get<ShoeJobHistoryEntry[]>(`/shoe-repair-jobs/${jobId}/status-history`)
export const claimShoeJob = (id: string) =>
  api.post<ShoeRepairJob>(`/shoe-repair-jobs/${id}/claim`)
export const releaseShoeJob = (id: string) =>
  api.post<ShoeRepairJob>(`/shoe-repair-jobs/${id}/release`)

export const addShoeToJob = (jobId: string, shoeId: string) =>
  api.post<ShoeRepairJob>(`/shoe-repair-jobs/${jobId}/shoes`, { shoe_id: shoeId })

export const appendShoeRepairJobItems = (jobId: string, items: ShoeRepairJobItemInput[]) =>
  api.post<ShoeRepairJob>(`/shoe-repair-jobs/${jobId}/items`, { items })

export const removeShoeFromJob = (jobId: string, entryId: string) =>
  api.delete<ShoeRepairJob>(`/shoe-repair-jobs/${jobId}/shoes/${entryId}`)

export const removeShoeRepairJobItem = (jobId: string, itemId: string) =>
  api.delete<ShoeRepairJob>(`/shoe-repair-jobs/${jobId}/items/${itemId}`)

export const getShoeJobMessages = (jobId: string) =>
  api.get<JobThreadMessage[]>(`/shoe-repair-jobs/${jobId}/messages`)
export const sendShoeJobMessage = (jobId: string, body: string) =>
  api.post<JobThreadMessage>(`/shoe-repair-jobs/${jobId}/messages`, { body })

export const cloneRepairJob = (jobId: string) =>
  api.post<RepairJob>(`/repair-jobs/${jobId}/clone`)
export const cloneAutoKeyJob = (jobId: string) =>
  api.post<AutoKeyJob>(`/auto-key-jobs/${jobId}/clone`)
export const cloneShoeRepairJob = (jobId: string) =>
  api.post<ShoeRepairJob>(`/shoe-repair-jobs/${jobId}/clone`)

export const getShoeJobSmsLog = (jobId: string) =>
  api.get<SmsLogEntry[]>(`/shoe-repair-jobs/${jobId}/sms-log`)

export const resendShoeNotification = (jobId: string, event: string) =>
  api.post<SmsLogEntry>(`/shoe-repair-jobs/${jobId}/resend-notification`, { event })

export const sendShoeQuote = (jobId: string) =>
  api.post<ShoeRepairJob>(`/shoe-repair-jobs/${jobId}/send-quote`)

export interface PublicShoeQuote {
  job_number: string
  title: string
  description?: string
  quote_status: string
  quote_approval_token_expires_at: string | null
  shop_name: string
  shoe: { shoe_type?: string; brand?: string; color?: string }
  items: Array<{ item_name: string; quantity: number; unit_price_cents: number | null; notes?: string }>
  subtotal_cents: number
}

export const getPublicShoeQuote = (token: string) =>
  axios.get<PublicShoeQuote>(withApiOrigin(`/v1/public/shoe-quotes/${token}`))

export const decideShoeQuote = (token: string, decision: 'approved' | 'declined', customer_signature_data_url?: string) =>
  axios.post<{ decision: string; job_number: string }>(withApiOrigin(`/v1/public/shoe-quotes/${token}/decision`), { decision, customer_signature_data_url })

export const createPortalSession = (email: string) =>
  axios.post<{ session_token: string; portal_url: string; expires_days: number }>(withApiOrigin('/v1/public/portal/create-session'), { email })

export const getPortalSession = (token: string, includeHistory = false) =>
  axios.get<CustomerPortalLookupResponse>(
    withApiOrigin(`/v1/public/portal/session/${token}`),
    includeHistory ? { params: { include_history: true } } : undefined,
  )

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

// ── Customer Account Statement / Invoices ────────────────────────────────────
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
  lines?: CustomerAccountStatementLine[]
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

// ── Watch Catalogue ──────────────────────────────────────────────────────────
export interface WatchCatalogueGroup {
  id: string
  label: string
}

export interface WatchCatalogueItem {
  key: string
  name: string
  price: number | null
  price_cents: number | null
  pricing_type: string
  group_id: string
  group_label: string
  notes?: string
}

export interface WatchMovement {
  key: string
  name: string
  purchase_cost_cents?: number
  quote_cents?: number
}

export interface WatchMovementsResponse {
  movements: WatchMovement[]
  currency?: string
  default_margin_percent?: number
  minimum_rrp_cents?: number
}

export interface WatchRepairsCombo {
  keys?: string[]
  total_cents?: number
  battery_key?: string
  band_keys?: string[]
  band_discount_percent?: number
}

export interface WatchRepairsConfig {
  combos: WatchRepairsCombo[]
  currency: string
}

export const listWatchCatalogueGroups = () =>
  api.get<WatchCatalogueGroup[]>('/watch-catalogue/groups')

export const searchWatchCatalogueItems = (params?: { q?: string; group?: string }) =>
  api.get<WatchCatalogueItem[]>('/watch-catalogue/items', { params })

export const listWatchMovements = () =>
  api.get<WatchMovementsResponse>('/watch-catalogue/movements')

export const getWatchRepairsConfig = () =>
  api.get<WatchRepairsConfig>('/watch-catalogue/repairs-config')

// ── Custom Services ───────────────────────────────────────────────────────────
export interface CustomServiceItem {
  id: string
  service_type: string
  name: string
  group_id: string
  group_label: string
  price_cents: number
  price?: number | null
  key?: string
  pricing_type: string
  notes?: string | null
}

export const listCustomServices = (service_type: 'watch' | 'shoe') =>
  api.get<CustomServiceItem[]>('/custom-services', { params: { service_type } })

export const createCustomService = (data: {
  service_type: 'watch' | 'shoe'
  name: string
  group_id?: string
  group_label?: string
  price_cents: number
  pricing_type?: string
  notes?: string | null
}) => api.post<CustomServiceItem>('/custom-services', data)

// ── Attachment helpers ────────────────────────────────────────────────────────
export async function resolveAttachmentDownloadUrl(storageKey: string): Promise<string> {
  const res = await api.get<AttachmentDownloadLinkResponse>(API_ROUTES.attachmentDownloadLink(storageKey))
  return res.data.download_url
}

export function getUploadErrorMessage(error: unknown, fallback = 'Upload failed.'): string {
  return getApiErrorMessage(error, fallback)
}

// ── Route optimisation ────────────────────────────────────────────────────────
export interface LatLng {
  lat: number
  lng: number
}

export interface OptimizeDrivingRouteResponse {
  visit_order: number[]
  source: 'trivial' | 'directions'
}

export const optimizeDrivingRoute = (stops: LatLng[]) =>
  api.post<OptimizeDrivingRouteResponse>('/maps/optimize-driving-route', { stops })

// ── Mobile commission helpers ─────────────────────────────────────────────────
export function buildMobileCommissionRulesJson(opts: {
  enabled: boolean
  retainerDollars: number
  shopPercent: number
  techSourcedPercent: number
  minitSourcedPercent: number
}): string {
  return JSON.stringify({
    enabled: opts.enabled,
    retainer_cents: Math.round(opts.retainerDollars * 100),
    shop_percent: opts.shopPercent,
    tech_sourced_percent: opts.techSourcedPercent,
    minit_sourced_percent: opts.minitSourcedPercent,
  })
}

export function isDuplicateTenantUserEmailError(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return false
  return error.response?.status === 409
}

// ── Pagination / sorting constants ───────────────────────────────────────────
export const DEFAULT_PAGE_SIZE = 50
export const WATCH_JOBS_LIST_MAX = 500
export type SortDir = 'asc' | 'desc'

// ── Mobile commission lead source options ─────────────────────────────────────
export const MOBILE_COMMISSION_LEAD_SOURCE_OPTIONS = [
  { value: 'shop', label: 'Shop (walk-in)' },
  { value: 'tech_sourced', label: 'Tech sourced' },
  { value: 'minit_sourced', label: 'Minit sourced' },
  { value: 'shop_referred', label: 'Shop referred' },
] as const

// ── SMS Log ──────────────────────────────────────────────────────────────────
export interface SmsLogEntry {
  id: string
  to_phone: string
  body: string
  event: string
  status: string
  created_at: string
}
export const getSmsLog = (jobId: string) =>
  api.get<SmsLogEntry[]>(`/repair-jobs/${jobId}/sms-log`)

export const resendJobNotification = (jobId: string, eventType: 'job_live' | 'job_ready' | 'quote_sent') =>
  api.post<{ sent: { sms: boolean; email: boolean } }>(`/repair-jobs/${jobId}/resend-notification`, { event_type: eventType })

// ── Job message thread ────────────────────────────────────────────────────────
export interface JobThreadMessage {
  id: string
  /** Backend declares this `str`; these are the only values it writes today. */
  direction: 'outbound' | 'inbound' | 'system' | (string & {})
  body: string
  from_phone?: string | null
  to_phone?: string | null
  event?: string | null
  status?: string | null
  created_at: string
}
export const getJobMessages = (jobId: string) =>
  api.get<JobThreadMessage[]>(`/repair-jobs/${jobId}/messages`)
export const sendJobMessage = (jobId: string, body: string) =>
  api.post<JobThreadMessage>(`/repair-jobs/${jobId}/messages`, { body })
export const getAutoKeyMessages = (jobId: string) =>
  api.get<JobThreadMessage[]>(`/auto-key-jobs/${jobId}/messages`)
export const sendAutoKeyMessage = (jobId: string, body: string) =>
  api.post<JobThreadMessage>(`/auto-key-jobs/${jobId}/messages`, { body })

// ── Inbox ─────────────────────────────────────────────────────────────────────
export interface InboxEvent {
  id: string
  tenant_id: string
  event_type: string
  event_summary: string
  entity_type?: string
  entity_id?: string
  created_at: string
}
export type GlobalSearchHit = {
  kind: string
  id: string
  title: string
  subtitle?: string | null
  status?: string | null
  href: string
}

export const globalSearch = (q: string, limit = 12) =>
  api.get<{ hits: GlobalSearchHit[] }>('/search', { params: { q, limit } })

export type NotificationPrefs = {
  email_quote_approved: boolean
  email_invoice_paid: boolean
  email_sms_reply: boolean
  email_daily_digest: boolean
  email_weekly_sales_report: boolean
  email_monthly_sales_report: boolean
  last_weekly_sales_report_sent_at: string | null
  last_monthly_sales_report_sent_at: string | null
}

export const getNotificationPreferences = () =>
  api.get<NotificationPrefs>('/me/notification-preferences')
export const patchNotificationPreferences = (body: Partial<NotificationPrefs>) =>
  api.patch<NotificationPrefs>('/me/notification-preferences', body)

export type IntegrationHealth = {
  twilio_configured: boolean
  last_sms_sent_at: string | null
  last_sms_failed_at: string | null
  stripe_configured: boolean
  stripe_connect_ready: boolean | null
  sendgrid_configured: boolean
  attachment_backend: string
}

export const getIntegrationHealth = () =>
  api.get<IntegrationHealth>('/tenant/integration-health')

export const mergeCustomers = (primaryId: string, duplicateId: string) =>
  api.post('/customers/merge', { primary_customer_id: primaryId, duplicate_customer_id: duplicateId })

export const bulkAutoKeyJobStatus = (jobIds: string[], status: string) =>
  api.post('/auto-key-jobs/bulk-status', { job_ids: jobIds, status })

export const exportRepairJobsCsv = () =>
  api.get<string>('/repair-jobs/export.csv', { responseType: 'text' })

export type JobTemplate = { id: string; label: string; module: string; title: string; pre_quote_cents: number }
export const listJobTemplates = () => api.get<JobTemplate[]>('/job-templates')

export const patchJobCustomFields = (
  jobType: 'repair_job' | 'auto_key_job' | 'shoe_repair_job',
  jobId: string,
  fields: Record<string, string>,
) => {
  const path =
    jobType === 'repair_job'
      ? `/repair-jobs/${jobId}/custom-fields`
      : jobType === 'auto_key_job'
        ? `/auto-key-jobs/${jobId}/custom-fields`
        : `/shoe-repair-jobs/${jobId}/custom-fields`
  return api.patch<{ ok: boolean; fields: Record<string, string> }>(path, { fields })
}

export type TenantApiKeyRow = { id: string; name: string; key_prefix: string; is_active: boolean; created_at: string }
export const listTenantApiKeys = () => api.get<TenantApiKeyRow[]>('/tenant/api-keys')
export const createTenantApiKey = (name: string) =>
  api.post<{ id: string; name: string; key_prefix: string; api_key: string }>('/tenant/api-keys', { name })
export const deleteTenantApiKey = (id: string) => api.delete(`/tenant/api-keys/${id}`)

export type TenantWebhookRow = { id: string; url: string; event_types: string; is_active: boolean; created_at: string }
export const listTenantWebhooks = () => api.get<TenantWebhookRow[]>('/tenant/webhooks')
export const createTenantWebhook = (url: string, eventTypes: string[]) =>
  api.post<TenantWebhookRow>('/tenant/webhooks', { url, event_types: eventTypes })
export const deleteTenantWebhook = (id: string) => api.delete(`/tenant/webhooks/${id}`)

export const patchPortalNotificationPrefs = (
  sessionToken: string,
  body: { status_notify_email?: boolean; status_notify_sms?: boolean },
) => api.patch(`/public/portal/session/${sessionToken}/preferences`, body)

export const portalMessageToShop = (
  sessionToken: string,
  body: { job_type: string; job_id: string; message: string },
) => api.post(`/public/portal/session/${sessionToken}/message-to-shop`, body)

export const getInbox = (limit = 50, offset = 0) => api.get<InboxEvent[]>('/inbox', { params: { limit, offset } })
export const getInboxCount = (exclude?: string[]) =>
  api.get<{ count: number }>('/inbox/count', {
    params: exclude?.length ? { exclude: exclude.join(',') } : undefined,
  })
export const deleteInboxEvent = (id: string) => api.delete(`/inbox/${id}`)

// ── Inbound email leads (BCC'd enquiry-form capture) ─────────────────────────
export interface InboundEmailListItem {
  id: string
  from_email?: string | null
  subject?: string | null
  /** Backend declares this `str`; these are the values it validates against today. */
  status: 'new' | 'processed' | 'dismissed' | (string & {})
  auto_key_job_id?: string | null
  created_at: string
}
export interface InboundEmailDetail extends InboundEmailListItem {
  to_email?: string | null
  message_id?: string | null
  text_body?: string | null
  html_body?: string | null
  spf_result?: string | null
  sender_ip?: string | null
}
export const listInboundEmails = (status?: string, limit = 50, offset = 0) =>
  api.get<InboundEmailListItem[]>('/parent-accounts/me/inbound-emails', {
    params: { ...(status ? { status } : {}), limit, offset },
  })
export const getInboundEmail = (id: string) =>
  api.get<InboundEmailDetail>(`/parent-accounts/me/inbound-emails/${id}`)
export const updateInboundEmailStatus = (id: string, status: 'new' | 'processed' | 'dismissed') =>
  api.patch<InboundEmailDetail>(`/parent-accounts/me/inbound-emails/${id}`, { status })

export interface InboundEmailParsed {
  fields_found: boolean
  location_state_raw?: string | null
  nearest_provider_raw?: string | null
  customer_name?: string | null
  email?: string | null
  phone?: string | null
  service_required?: string | null
  vehicle_make?: string | null
  vehicle_model?: string | null
  vehicle_year?: string | null
  details?: string | null
  contact_preference?: string | null
  suggested_operator_tenant_id?: string | null
  suggested_operator_name?: string | null
  match_confidence: string
}
export interface InboundEmailJobCreateRequest {
  customer_name: string
  phone?: string | null
  email?: string | null
  suburb?: string | null
  state_code?: string | null
  service_required?: string | null
  vehicle_make?: string | null
  vehicle_model?: string | null
  vehicle_year?: string | null
  details?: string | null
  contact_preference?: string | null
  target_tenant_id?: string | null
}
export interface InboundEmailJobCreateResult {
  inbound_email_id: string
  auto_key_job_id: string
  job_number: string
  tenant_id: string
  tenant_name: string
}
export const getInboundEmailParsed = (id: string) =>
  api.get<InboundEmailParsed>(`/parent-accounts/me/inbound-emails/${id}/parsed`)
export const createJobFromInboundEmail = (id: string, body: InboundEmailJobCreateRequest) =>
  api.post<InboundEmailJobCreateResult>(`/parent-accounts/me/inbound-emails/${id}/create-job`, body)

// ── Auto-key attachments & SMS ────────────────────────────────────────────────
export const listAutoKeyAttachments = (jobId: string) =>
  api.get<Attachment[]>('/attachments', { params: { auto_key_job_id: jobId } })

export const uploadAutoKeyAttachment = (file: File, jobId: string, label?: string) => {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams({ auto_key_job_id: jobId })
  if (label) params.append('label', label)
  return api.post<Attachment>(`/attachments?${params.toString()}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

export const sendAutoKeyArrivalSms = (jobId: string, time_window?: string) =>
  api.post<{ ok: boolean }>(`/auto-key-jobs/${jobId}/arrival-sms`, time_window ? { time_window } : undefined)

export const sendAutoKeyDayBeforeReminders = () =>
  api.post<{ sent: number }>('/auto-key-jobs/day-before-reminders')

export interface AutoKeyInvoiceUpdatePayload {
  status?: string
  notes?: string
  payment_method?: string | null
  subtotal_cents?: number
  tax_cents?: number
  total_cents?: number
  currency?: string
}
export const updateAutoKeyInvoice = (_jobId: string, invoiceId: string, data: AutoKeyInvoiceUpdatePayload) =>
  api.patch<AutoKeyInvoice>(`/auto-key-jobs/invoices/${invoiceId}`, data)

export const createAutoKeyQuickIntake = (data: { full_name: string; phone: string }) =>
  api.post<AutoKeyJob>('/auto-key-jobs/quick-intake', data)

// ── Auto-key reports ──────────────────────────────────────────────────────────
export interface AutoKeyReportSummary {
  total_jobs: number
  total_revenue_cents: number
  avg_job_value_cents: number
  mobile_count: number
  mobile_pct: number
  shop_count: number
  shop_pct: number
  mobile_revenue_cents: number
  mobile_revenue_pct: number
  shop_revenue_cents: number
  shop_revenue_pct: number
}

export interface AutoKeyReportKpis {
  same_day_invoice_rate_pct: number
  same_day_invoiced_count: number
  invoiced_completed_count: number
  lead_to_quote_pct: number
  quoted_jobs_count: number
  avg_cycle_hours: number | null
  completed_jobs_count: number
  schedule_adherence_pct: number
  on_time_count: number
  scheduled_completed_count: number
}

export interface AutoKeyReports {
  summary: AutoKeyReportSummary
  financials?: {
    invoiced_cents: number
    paid_cents: number
    outstanding_cents: number
    invoice_count: number
    paid_invoice_count: number
    outstanding_invoice_count: number
    deposits_cents: number
  }
  pipeline?: {
    quote_count: number
    quote_value_cents: number
    approved_quote_count: number
    approved_quote_value_cents: number
  }
  operations?: {
    unassigned_active: number
    unscheduled_active: number
    urgent_active: number
  }
  previous_period?: {
    date_from: string
    date_to: string
    jobs: number
    invoiced_cents: number
    paid_cents: number
    quotes: number
    quote_value_cents: number
  } | null
  kpis?: AutoKeyReportKpis
  jobs_by_type: Array<{ job_type: string; jobs: number; revenue_cents: number; avg_value_cents: number }>
  jobs_by_tech: Array<{ tech_id: string; tech_name: string; job_count: number; revenue_cents: number; revenue_share_pct?: number }>
  jobs_by_status: Array<{ status: string; count: number; label?: string }>
  week_on_week: Array<{ week_start?: string; week_label?: string; jobs: number; revenue_cents: number }>
}

export interface AutoKeyCommissionTechLine {
  job_id: string
  invoice_id: string
  job_number: string
  lead_source_label: string
  revenue_cents: number
  rate_bp: number
  commission_cents: number
}

export interface AutoKeyCommissionTech {
  user_id: string
  full_name: string
  bonus_payable_cents: number
  raw_commission_cents: number
  retainer_cents: number
  lines: AutoKeyCommissionTechLine[]
}

export interface AutoKeyCommissionReport {
  technicians: AutoKeyCommissionTech[]
}

export const getAutoKeyReports = (params?: { date_from?: string; date_to?: string }) =>
  api.get<AutoKeyReports>('/reports/auto-key', { params })

// ── Mobile Services operations cockpit ─────────────────────────────────────
export type MobileStatusCategoryKey = 'pipeline' | 'booking' | 'field' | 'completed' | 'paid' | 'lost'
export type MobileCockpitFocusKey =
  | 'late'
  | 'today'
  | 'in_field'
  | 'unscheduled'
  | 'unassigned'
  | 'on_hold'
  | 'needs_quote'
  | 'quote_follow_up'
  | 'confirmation_follow_up'
  | 'completed_unpaid'
  | 'overdue_invoices'
  | 'unpaid_invoices'
  | 'this_week'
  | 'completed_this_week'
  | 'invoiced_this_week'
  | 'collected_this_week'
export type MobileCockpitTone = 'bad' | 'warn' | 'good' | 'neutral'
export type MobileCockpitDirection = 'higher_is_better' | 'lower_is_better' | 'neutral'

export interface MobileCockpitJobSummary {
  id: string
  job_number: string
  title: string
  customer_name: string | null
  customer_phone: string | null
  status: JobStatus
  canonical_status: JobStatus
  category: MobileStatusCategoryKey | null
  priority: string
  scheduled_at: string | null
  assigned_user_id: string | null
  assigned_name: string | null
  job_address: string | null
  cost_cents: number
  created_at: string | null
}

export interface MobileCockpitQueue {
  key: MobileCockpitFocusKey
  label: string
  description: string
  tone: MobileCockpitTone
  count: number
  directory: 'active' | 'completed' | 'all'
  items: MobileCockpitJobSummary[]
}

export interface MobileCockpitDelta {
  abs: number
  /** null when the baseline is zero (nothing to compare against). */
  pct: number | null
}

export interface MobileCockpitMetric {
  key: 'booked' | 'completed' | 'invoiced' | 'collected' | 'jobs_created' | 'jobs_completed'
  label: string
  unit: 'cents' | 'count'
  definition: string
  direction: MobileCockpitDirection
  /** True while the week is incomplete: comparisons are to the same days of prior periods. */
  partial: boolean
  days_elapsed: number
  current: number
  previous: number
  previous_to_date: number
  four_week_avg: number
  four_week_avg_to_date: number
  target: number | null
  target_to_date: number | null
  vs_previous: MobileCockpitDelta | null
  vs_previous_tone: MobileCockpitTone
  vs_four_week: MobileCockpitDelta | null
  vs_four_week_tone: MobileCockpitTone
  vs_target: MobileCockpitDelta | null
  vs_target_tone: MobileCockpitTone
}

export interface MobileCockpitTechnician {
  user_id: string
  name: string
  role: string
  scheduled_today: number
  booked_minutes_today: number
  capacity_minutes: number
  available_minutes: number
  utilisation_pct: number
  active_jobs: number
  in_field_now: boolean
  current_job_number: string | null
  late_today: number
  conflicts: Array<{ job_id: string; job_number: string; next_job_id: string; next_job_number: string; gap_minutes: number }>
  next_job: { id: string; job_number: string; scheduled_at: string; job_address: string | null } | null
  collected_week_cents: number
  completed_week: number
}

export interface MobileCockpitOverdueItem extends MobileCockpitJobSummary {
  invoice_id: string
  invoice_number: string
  invoice_total_cents: number
  invoice_age_days: number
}

export interface MobileCockpit {
  as_of: string
  timezone: string
  generated_at: string
  week: { start: string; end: string; days_elapsed: number; complete: boolean }
  attention: MobileCockpitQueue[]
  follow_ups: {
    quotes: MobileCockpitQueue & { value_cents: number; open_count: number }
    confirmations: MobileCockpitQueue & { open_count: number }
    completed_unpaid: MobileCockpitQueue & { value_cents: number }
    overdue_invoices: Omit<MobileCockpitQueue, 'items'> & { value_cents: number; items: MobileCockpitOverdueItem[] }
  }
  metrics: MobileCockpitMetric[]
  outstanding: {
    key: 'outstanding'
    label: string
    unit: 'cents'
    direction: 'lower_is_better'
    definition: string
    current: number
    count: number
    aging_cents: { current: number; d8_30: number; d31_plus: number }
    aging_counts: { current: number; d8_30: number; d31_plus: number }
    overdue_cents: number
  }
  technicians: MobileCockpitTechnician[]
  capacity: {
    technicians: number
    capacity_minutes: number
    booked_minutes: number
    available_minutes: number
    conflicts: number
    unassigned_today: number
  }
  active_by_category: Array<{ category: MobileStatusCategoryKey; label: string; count: number }>
  period_drill: Partial<Record<MobileCockpitFocusKey, { count: number; directory: 'active' | 'completed' | 'all' }>>
  assumptions: {
    assumed_job_minutes: number
    tech_day_minutes: number
    quote_follow_up_days: number
    confirmation_follow_up_hours: number
    invoice_overdue_days: number
  }
  weekly_target_cents: number | null
  data_quality: Array<{ code: string; message: string; count: number | null }>
}

// ── Mobile Services finance report ─────────────────────────────────────────
export type MobileFinancePreset = 'week' | 'last_week' | 'month' | 'last_month' | 'quarter' | 'last_4_weeks' | 'last_13_weeks' | 'custom'
export type MobileFinanceDateField = 'created' | 'scheduled' | 'completed' | 'invoiced' | 'paid'

export interface MobileFinanceDrill {
  date_field?: MobileFinanceDateField
  date_from?: string
  date_to?: string
  directory?: 'active' | 'completed' | 'all'
  focus?: MobileCockpitFocusKey
}

export interface MobileFinanceMetric {
  key: 'booked' | 'completed' | 'invoiced' | 'collected' | 'outstanding' | 'commission' | 'contribution' | 'aov' | 'jobs_completed' | 'jobs_per_working_day' | 'jobs_created' | 'quotes_sent'
  label: string
  unit: 'cents' | 'count' | 'pct' | 'minutes'
  definition: string
  direction: MobileCockpitDirection
  /** null = not available (e.g. no commission rules, no paid invoices). */
  current: number | null
  previous: number | null
  vs_previous: MobileCockpitDelta | null
  vs_previous_tone: MobileCockpitTone
  drill: MobileFinanceDrill | null
  sample: number | null
}

export interface MobileFinanceDurationStats {
  count: number
  avg_minutes: number | null
  median_minutes: number | null
  p90_minutes: number | null
}

export interface MobileFinanceTechnician {
  user_id: string
  name: string
  jobs_scheduled: number
  jobs_completed: number
  invoiced_cents: number
  collected_cents: number
  commission_cents: number
  booked_minutes: number
  capacity_minutes: number
  utilisation_pct: number | null
  revenue_per_job_cents: number | null
  on_site: MobileFinanceDurationStats
}

export interface MobileFinanceReport {
  preset: MobileFinancePreset
  timezone: string
  generated_at: string
  period: {
    label: string
    start: string
    end: string
    days: number
    elapsed_days: number
    working_days: number
    complete: boolean
    previous_start: string
    previous_end: string
  }
  metrics: MobileFinanceMetric[]
  target: {
    weekly_cents: number
    period_cents: number
    to_date_cents: number
    collected_cents: number
    variance_cents: number
    attainment_pct: number | null
    tone: MobileCockpitTone
  } | null
  conversion: Array<{
    key: 'quote_to_approved' | 'lead_to_booking' | 'booking_to_completion'
    label: string
    numerator: number
    denominator: number
    pct: number | null
    previous_pct: number | null
    definition: string
    vs_previous_tone: MobileCockpitTone
  }>
  ar_ageing: {
    total_cents: number
    overdue_cents: number
    overdue_pct: number | null
    buckets: Array<{ key: string; label: string; cents: number; count: number }>
    open_invoices: Array<{ invoice_id: string; invoice_number: string; job_id: string; job_number: string; customer_name: string | null; total_cents: number; age_days: number; raised_on: string | null }>
  }
  trend: {
    weeks: Array<{ week_start: string; booked_cents: number; completed_cents: number; invoiced_cents: number; collected_cents: number; jobs_completed: number; jobs_created: number }>
    averages: Record<'booked_cents' | 'completed_cents' | 'invoiced_cents' | 'collected_cents' | 'jobs_completed' | 'jobs_created', { last_4_avg: number | null; last_13_avg: number | null; latest: number | null }>
  }
  technicians: MobileFinanceTechnician[]
  durations: {
    estimated_minutes: number
    estimate_source: 'assumed'
    on_site: MobileFinanceDurationStats
    travel: MobileFinanceDurationStats
    by_job_type: Array<{ job_type: string } & MobileFinanceDurationStats>
  }
  definitions: Record<string, string>
  data_quality: Array<{ code: string; message: string; count: number | null }>
}

export type MobileFinanceParams = { period: MobileFinancePreset; date_from?: string; date_to?: string }
export const getAutoKeyFinance = (params: MobileFinanceParams) =>
  api.get<MobileFinanceReport>('/reports/auto-key/finance', { params })
export const autoKeyFinanceExportUrl = (params: MobileFinanceParams & { kind: 'summary' | 'invoices' }) =>
  withApiOrigin(`/v1/reports/auto-key/finance/export?${new URLSearchParams(Object.entries(params).filter(([, v]) => v != null) as [string, string][]).toString()}`)
export const downloadAutoKeyFinanceExport = (params: MobileFinanceParams & { kind: 'summary' | 'invoices' }) =>
  api.get<Blob>('/reports/auto-key/finance/export', { params, responseType: 'blob' })

export const getAutoKeyCockpit = (params?: { as_of?: string; items?: number }) =>
  api.get<MobileCockpit>('/reports/auto-key/cockpit', { params })
export const setAutoKeyWeeklyTarget = (weekly_target_cents: number | null) =>
  api.patch<{ weekly_target_cents: number | null }>('/reports/auto-key/cockpit/target', { weekly_target_cents })

export const getAutoKeyCommissionReport = (params?: { date_from?: string; date_to?: string }) =>
  api.get<AutoKeyCommissionReport>('/reports/auto-key/commission', { params })

export interface AutoKeyQuoteSuggestionResult {
  total_cents: number
  line_items: AutoKeyQuoteLineItem[]
}
export type AutoKeyPricingTier = 'retail' | 'b2b' | 'tier1' | 'tier2' | 'tier3'
export const getAutoKeyQuoteSuggestions = (params: { job_type?: string; key_quantity?: number; pricing_tier?: AutoKeyPricingTier; additional_presets?: string[] }) => {
  const { additional_presets, ...rest } = params
  const p = { ...rest, ...(additional_presets?.length ? { additional_presets: additional_presets.join(',') } : {}) }
  return api.get<AutoKeyQuoteSuggestionResult & { pricing_tier: string }>('/auto-key-jobs/quote-suggestions', { params: p })
}

// ── Vehicle key specs ─────────────────────────────────────────────────────────
export interface VehicleKeySpecMatch {
  score: number
  label: string
  vehicle_make: string
  vehicle_model: string
  year_from?: number | null
  year_to?: number | null
  years_label?: string
  key_type?: string | null
  chip_type?: string | null
  tech_notes?: string
  key_blanks?: Array<{ primary_code?: string; blank_reference?: string }>
  suggested_blade_code?: string
  // v3 structured flags
  akl_complexity?: string | null
  bsu_required?: boolean
  pin_required?: boolean
  eeprom_required?: boolean
  obd_programmable?: boolean
  dealer_required?: boolean
}
export const searchVehicleKeySpecs = (params: { make?: string; model?: string; year?: number }) =>
  api.get<{ matches: VehicleKeySpecMatch[] }>('/vehicle-key-specs/search', { params })

export interface KnownIssue {
  make?: string
  model?: string
  variant?: string
  issue?: string
  severity?: string
  notes?: string
  resolution?: string
}

export interface ToolRecommendation {
  make?: string
  model?: string
  job_type?: string
  primary_tool?: string
  backup_tool?: string
  escalation_tool?: string
  risk_level?: string
  notes?: string
}

export interface CuttingProfile {
  blank_reference?: string
  description?: string
  key_type?: string
  common_makes_models?: string
  dolphin_xp005l?: string
  condor_xc_mini_plus_ii?: string
  silca_alpha_pro?: string
  silca_futura_pro?: string
  notes?: string
}

export interface VehicleJobContext {
  complexity: string | null
  known_issues: KnownIssue[]
  tool_recommendations: ToolRecommendation[]
  cutting_profiles: CuttingProfile[]
}

export const getVehicleJobContext = (params: { make?: string; model?: string; year?: number; job_type?: string; blade_code?: string }) =>
  api.get<VehicleJobContext>('/vehicle-key-specs/job-context', { params })

// ── Billing — Stripe Connect ──────────────────────────────────────────────────
export const refreshStripeConnectStatus = () =>
  api.post<BillingLimitsResponse>('/billing/connect/refresh')
export const createStripeConnectAccountLink = () =>
  api.post<{ url: string }>('/billing/connect/account-link')

// ── Billing — Xero (Mobile Services invoices) ─────────────────────────────────
export interface XeroConnectionStatus {
  configured: boolean
  connected: boolean
  connection_status?: string | null
  xero_tenant_id?: string | null
  default_sales_account_code?: string | null
  default_tax_type?: string | null
}

export const getXeroConnectionStatus = () =>
  api.get<XeroConnectionStatus>('/billing/xero/status')
export const getXeroConnectUrl = () => api.get<{ url: string }>('/billing/xero/connect')
export const disconnectXero = () => api.post<XeroConnectionStatus>('/billing/xero/disconnect')
export const retryAutoKeyInvoiceXeroSync = (invoiceId: string) =>
  api.post<AutoKeyInvoice>(`/auto-key-jobs/invoices/${invoiceId}/xero/retry`)

// ── Users — delete ────────────────────────────────────────────────────────────
export const deleteUser = (userId: string) => api.delete(`/users/${userId}`)

// ── Prospects ─────────────────────────────────────────────────────────────────
export interface Prospect {
  name: string
  address: string
  phone?: string | null
  website?: string | null
  rating?: number | null
  review_count?: number | null
  category: string
  place_id: string
}
export interface ProspectSearchResponse {
  results: Prospect[]
  total: number
  category: string
}
export const getProspectCollectorStatus = () =>
  api.get<{ enabled: boolean; remaining: number; total: number }>('/prospects/collector-status')
export const listProspectCategories = () =>
  api.get<{ categories: Array<{ key: string; label: string }> }>('/prospects/categories')
export const listProspectRegions = () =>
  api.get<{ states: Array<{ code: string; name: string }>; suburbs: Record<string, string[]>; region_groups: Record<string, Record<string, string[]>> }>('/prospects/regions')
export const searchProspects = (category: string, state: string, suburbs?: string[], live?: boolean) =>
  api.get<ProspectSearchResponse>('/prospects/search', {
    params: { category, state, suburbs: suburbs?.join(',') || undefined, live },
  })

// ── Prospect Leads (CRM board) ────────────────────────────────────────────────
export type ProspectLeadStatus = 'new' | 'contacted' | 'visited' | 'onboarded'
export interface ProspectLead {
  id: string
  tenant_id: string
  place_id?: string | null
  name: string
  address?: string | null
  phone?: string | null
  website?: string | null
  rating?: number | null
  review_count?: number | null
  category?: string | null
  state_code?: string | null
  contact_name?: string | null
  contact_email?: string | null
  notes?: string | null
  status: ProspectLeadStatus
  visit_scheduled_at?: string | null
  customer_account_id?: string | null
  created_at: string
  updated_at: string
}
export const listProspectLeads = () =>
  api.get<ProspectLead[]>('/prospect-leads')
export const saveProspectLead = (data: {
  place_id?: string; name: string; address?: string; phone?: string
  website?: string; rating?: number; review_count?: number
  category?: string; state_code?: string
}) => api.post<ProspectLead>('/prospect-leads', data)
export const updateProspectLead = (id: string, data: {
  contact_name?: string; contact_email?: string; notes?: string
  status?: ProspectLeadStatus; visit_scheduled_at?: string | null
}) => api.patch<ProspectLead>(`/prospect-leads/${id}`, data)
export const advanceProspectLead = (id: string) =>
  api.post<ProspectLead>(`/prospect-leads/${id}/advance`)
export const deleteProspectLead = (id: string) =>
  api.delete(`/prospect-leads/${id}`)

// ── Inbound lead inbox (/v1/prospects/leads) ──────────────────────────────────
export type InboundLeadStatus = 'new' | 'quote_needed' | 'contacted' | 'follow_up_due' | 'won' | 'lost'
export interface InboundLead {
  id: string
  tenant_id: string
  place_id?: string | null
  name: string
  address?: string | null
  phone?: string | null
  website?: string | null
  rating?: number | null
  review_count?: number | null
  category?: string | null
  state_code?: string | null
  suburb_name?: string | null
  contact_name?: string | null
  contact_email?: string | null
  notes?: string | null
  status: InboundLeadStatus
  /** 'prospected' (found via Prospects search) | 'website_lead' (routed from the website enquiry feed) */
  source?: string
  next_follow_up_on?: string | null
  visit_scheduled_at?: string | null
  customer_account_id?: string | null
  created_at: string
  updated_at: string
}
export const listInboundLeads = (status?: InboundLeadStatus) =>
  api.get<InboundLead[]>('/prospects/leads', { params: status ? { status } : undefined })
export const createInboundLead = (data: {
  name: string; phone?: string; address?: string; category?: string
  state_code?: string; suburb_name?: string; website?: string
  contact_name?: string; contact_email?: string; notes?: string; status?: InboundLeadStatus
}) => api.post<InboundLead>('/prospects/leads', data)
export const updateInboundLead = (id: string, data: {
  status?: InboundLeadStatus; notes?: string; contact_name?: string
  contact_email?: string; phone?: string; next_follow_up_on?: string | null
}) => api.patch<InboundLead>(`/prospects/leads/${id}`, data)
export const convertInboundLeadToAccount = (id: string, data: {
  account_name: string; contact_name?: string; contact_phone?: string; contact_email?: string
}) => api.post<InboundLead>(`/prospects/leads/${id}/convert-to-account`, data)

// ── Parent account — mobile lead ingest ──────────────────────────────────────
export interface MobileSuburbRoute {
  id: string
  suburb_name?: string
  suburb_normalized?: string
  state_code: string
  tenant_id?: string
  target_tenant_id: string
}
export interface MobileSuburbRouteOperatorSummary {
  target_tenant_id: string
  operator_name: string
  operator_slug: string
  operator_shop_number?: string | null
  route_count: number
}
export interface MobileSuburbRoutesSummary {
  total_routes: number
  operators: MobileSuburbRouteOperatorSummary[]
}
export interface ParentRoutingTestResult {
  suburb: string
  state_code: string
  suburb_normalized: string
  routing_rule: string
  operator_tenant_id?: string | null
  operator_slug?: string | null
  operator_name?: string | null
  operator_shop_number?: string | null
  message?: string | null
}
export const listMobileSuburbRoutes = (params?: { search?: string; limit?: number }) =>
  api.get<MobileSuburbRoute[]>('/parent-accounts/me/mobile-lead-routes', { params })
export const getMobileSuburbRoutesSummary = () =>
  api.get<MobileSuburbRoutesSummary>('/parent-accounts/me/mobile-lead-routes/summary')
export const testMobileLeadRouting = (params: { suburb: string; state_code: string }) =>
  api.get<ParentRoutingTestResult>('/parent-accounts/me/routing/test', { params })
export const setParentMobileLeadDefaultTenant = (tenant_id: string | null) =>
  api.put('/parent-accounts/me/mobile-lead-ingest/default-tenant', { tenant_id })
export const setParentMobileLeadEscalationTenant = (tenant_id: string | null) =>
  api.put<ParentLeadIngestConfig>('/parent-accounts/me/mobile-lead-ingest/escalation-tenant', { tenant_id })
export const setParentMobileLeadDispatchSettings = (data: {
  offer_timeout_minutes?: number
  max_operator_offers?: number
  force_hq_dispatch?: boolean
}) => api.put<ParentLeadIngestConfig>('/parent-accounts/me/mobile-lead-ingest/dispatch-settings', data)
export const setParentMobileLeadWebhookSecret = (secret: string) =>
  api.put('/parent-accounts/me/mobile-lead-ingest/secret', { webhook_secret: secret })
export const clearParentMobileLeadWebhookSecret = () =>
  api.delete('/parent-accounts/me/mobile-lead-ingest/secret')
export const setParentInboundEmailSecret = (secret: string) =>
  api.put<ParentLeadIngestConfig>('/parent-accounts/me/inbound-email/secret', { webhook_secret: secret })
export const clearParentInboundEmailSecret = () =>
  api.delete<ParentLeadIngestConfig>('/parent-accounts/me/inbound-email/secret')
export const createMobileSuburbRoute = (data: { suburb: string; state_code: string; target_tenant_id: string }) =>
  api.post<MobileSuburbRoute>('/parent-accounts/me/mobile-lead-routes', data)
export const deleteMobileSuburbRoute = (id: string) =>
  api.delete(`/parent-accounts/me/mobile-lead-routes/${id}`)
export const enableParentMobileLeadIngest = () =>
  api.post('/parent-accounts/me/mobile-lead-ingest/enable')

// ── Toolkit ───────────────────────────────────────────────────────────────────
export interface ToolkitTool {
  key: string
  name: string
  notes?: string
  group_label?: string
}
export interface ToolkitGroup {
  id: string
  label: string
  tools: ToolkitTool[]
}
export interface ToolkitRecommendResponse {
  scenario_id: string
  label?: string
  ready_for_required?: boolean
  tips?: string
  recommended_tool_keys: string[]
  missing: string[]
  have: string[]
  missing_required: Array<{ key: string; name: string; group_label?: string }>
  missing_nice_to_have: Array<{ key: string; name: string }>
  required: Array<{ key: string; name: string; via_alternative?: boolean }>
}
export const getToolkitCatalog = () =>
  api.get<{ groups: ToolkitGroup[]; scenarios: Array<{ id: string; label: string }> }>('/toolkit/catalog')
export const getToolkitMySelection = () =>
  api.get<{ tool_keys: string[] }>('/toolkit/my-selection')
export const putToolkitMySelection = (tool_keys: string[]) =>
  api.put('/toolkit/my-selection', { tool_keys })
export interface MobileCatalogueRead {
  enabled_categories: MobileCatalogueCategory[]
  available_categories: Array<{ key: MobileCatalogueCategory; label: string; description: string }>
}
export const getToolkitMobileCatalogue = () => api.get<MobileCatalogueRead>('/toolkit/mobile-catalogue')
export const patchToolkitMobileCatalogue = (enabled_categories: MobileCatalogueCategory[]) =>
  api.patch<MobileCatalogueRead>('/toolkit/mobile-catalogue', { enabled_categories })
export const getToolkitMobileNotifications = () =>
  api.get<{ customer_sms_enabled: boolean; dispatch_phone: string | null }>('/toolkit/mobile-notifications')
export const patchToolkitMobileNotifications = (payload: {
  customer_sms_enabled?: boolean
  dispatch_phone?: string | null
}) =>
  api.patch<{ customer_sms_enabled: boolean; dispatch_phone: string | null }>(
    '/toolkit/mobile-notifications',
    payload,
  )
export const recommendToolkit = (scenario_id: string) =>
  api.post<ToolkitRecommendResponse>('/toolkit/recommend', { scenario_id })
export const postToolkitRecommend = recommendToolkit

// ── Watch movement quote ──────────────────────────────────────────────────────
export const getWatchMovementQuote = (key: string) =>
  api.get<{ quote_cents: number; cost_cents?: number }>(`/watch-catalogue/movements/${key}/quote`)

// ── Public auto-key intake / invoice pages ─────────────────────────────────────
export interface PublicAutoKeyIntake {
  job_id: string
  status_token: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number
  registration_plate?: string
  key_type?: string
  description?: string
  job_address?: string
  job_type?: string
  shop_name?: string
  job_number?: string
  customer_first_name_hint?: string
}
export const getPublicAutoKeyIntake = (token: string) =>
  axios.get<PublicAutoKeyIntake>(withApiOrigin(`/v1/public/auto-key-intake/${token}`))
export const uploadPublicAutoKeyIntakePhotos = (token: string, files: File[]) => {
  const form = new FormData()
  files.forEach(file => form.append('files', file))
  return axios.post<{ ok: boolean; count: number; attachment_ids: string[] }>(
    withApiOrigin(`/v1/public/auto-key-intake/${token}/photos`),
    form,
    { timeout: 120000 },
  )
}
export const submitPublicAutoKeyIntake = (token: string, data: {
  full_name?: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number
  registration_plate?: string
  vin?: string
  job_address?: string
  job_type?: string
  additional_services?: Array<{ preset?: string; custom?: string }>
  scheduled_at?: string
  description?: string
  key_quantity?: number
  key_type?: string
  blade_code?: string
  chip_type?: string
  tech_notes?: string
  key_photo_data?: string
  extra_key_photo_data?: string
}) => axios.post<{ message?: string }>(withApiOrigin(`/v1/public/auto-key-intake/${token}/submit`), data)

export interface PublicAutoKeyInvoice {
  invoice_number: string
  total_cents: number
  subtotal_cents: number
  tax_cents: number
  status: string
  currency: string
  created_at: string
  line_items: AutoKeyQuoteLineItem[]
  can_pay_online?: boolean
  shop_name?: string
  job_number?: string
  job_title?: string
}
export const getPublicAutoKeyInvoice = (token: string) =>
  axios.get<PublicAutoKeyInvoice>(API_ROUTES.publicAutoKeyInvoice(token))
export const createPublicAutoKeyInvoiceCheckout = (token: string) =>
  axios.post<{ checkout_url: string }>(API_ROUTES.publicAutoKeyInvoiceCheckout(token))

export interface PublicAutoKeyBooking {
  job_id: string
  status_token: string
  job_number: string
  title: string
  status: string
  scheduled_at?: string
  job_address?: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number
  registration_plate?: string
  line_items: AutoKeyQuoteLineItem[]
  currency: string
  quote_total_cents: number
  already_confirmed?: boolean
  awaiting_confirmation?: boolean
}
export const getPublicAutoKeyBooking = (token: string) =>
  axios.get<PublicAutoKeyBooking>(API_ROUTES.publicAutoKeyBooking(token))
export const confirmPublicAutoKeyBooking = (token: string, body?: { signatureData?: string; signerName?: string }) =>
  axios.post<PublicAutoKeyBooking>(API_ROUTES.publicAutoKeyBookingConfirm(token), {
    signature_data: body?.signatureData,
    signer_name: body?.signerName,
  })

export interface PublicAutoKeyQuote {
  quote_id: string
  status: string
  job_number: string
  title: string
  vehicle_make: string | null
  vehicle_model: string | null
  vehicle_year: number | null
  job_address: string | null
  scheduled_at: string | null
  shop_name: string
  shop_phone: string | null
  customer_name: string | null
  subtotal_cents: number
  tax_cents: number
  total_cents: number
  currency: string
  signed_at: string | null
  signer_name: string | null
  has_signature: boolean
  line_items: { description: string; quantity: number; unit_price_cents: number; total_price_cents: number }[]
}

export const getPublicAutoKeyQuote = (token: string) =>
  axios.get<PublicAutoKeyQuote>(withApiOrigin(`/v1/public/auto-key-quote/${token}`))
export const decidePublicAutoKeyQuote = (
  token: string,
  decision: 'approved' | 'declined',
  opts?: { signatureData?: string; signerName?: string }
) =>
  axios.post<{ ok: boolean; status: string; message: string }>(
    withApiOrigin(`/v1/public/auto-key-quote/${token}/decision`),
    { decision, signature_data: opts?.signatureData, signer_name: opts?.signerName }
  )

export interface PublicAutoKeyJobStatus {
  job_id?: string
  job_number: string
  title: string
  status: string
  description?: string | null
  vehicle_make?: string | null
  vehicle_model?: string | null
  vehicle_year?: number | null
  job_address?: string | null
  scheduled_at?: string | null
  created_at: string
  shop_name: string
  shop_phone?: string | null
  shop_email?: string | null
  quote_total_cents: number
  currency: string
  pending_actions: CustomerPortalPendingAction[]
}

export const getPublicAutoKeyJobStatus = (token: string) =>
  axios.get<PublicAutoKeyJobStatus>(withApiOrigin(`/v1/public/auto-key-jobs/${token}`))

// ── Loyalty ───────────────────────────────────────────────────────────────────

export interface LoyaltyTierInfo {
  id: number
  tier_name: string
  tier_label: string
}

export interface CustomerLoyaltyRead {
  customer_id: string
  tier_id: number
  tier_name: string
  tier_label: string
  points_balance: number
  points_dollar_value: number
  rolling_12m_spend_cents: number
  joined_at: string
}

export interface PointsLedgerEntry {
  id: string
  entry_type: string
  points_delta: number
  source_invoice_id: string | null
  note: string | null
  occurred_at: string
}

export interface LoyaltyProfileResponse {
  loyalty: CustomerLoyaltyRead
  recent_ledger: PointsLedgerEntry[]
}

export const getLoyaltyProfile = (customerId: string) =>
  api.get<LoyaltyProfileResponse>(`/loyalty/customers/${customerId}`)

export const adjustLoyaltyPoints = (customerId: string, points_delta: number, note: string) =>
  api.post<LoyaltyProfileResponse>(`/loyalty/customers/${customerId}/adjust`, { points_delta, note })

// ── Intake dispatch (ring-map job pool) ──────────────────────────────────────

export interface IntakePoolJob {
  id: string
  customer_name: string
  job_address: string
  vehicle_make: string | null
  vehicle_model: string | null
  vehicle_year: string | null
  registration_plate: string | null
  description: string | null
  ring: number
  created_at: string
}

export interface SubmitIntakeBody {
  customer_name: string
  customer_phone?: string
  customer_email?: string
  job_address: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: string
  registration_plate?: string
  description?: string
}

export const submitPublicIntake = (body: SubmitIntakeBody) =>
  axios.post<{ id: string; message: string }>(withApiOrigin('/v1/public/intake'), body)

export const listJobPool = (maxRing?: number) =>
  api.get<IntakePoolJob[]>('/pool', { params: maxRing != null ? { max_ring: maxRing } : undefined })

export const claimPoolJob = (jobId: string) =>
  api.post<{ message: string; auto_key_job_id: string; job_number: string; customer_id: string }>(`/pool/${jobId}/claim`)

export const setDispatchBaseLocation = (address: string, ring_radius_km = 10) =>
  api.post<{ base_lat: number; base_lng: number; ring_radius_km: number }>('/settings/dispatch-base-location', { address, ring_radius_km })

export interface ShopIdentity {
  name: string
  abn?: string | null
  shop_phone?: string | null
  shop_email?: string | null
  payment_instructions?: string | null
  business_address?: string | null
  logo_url?: string | null
  brand_color?: string | null
  /** Minit shop number (e.g. "3269") — links this shop to Minit HQ regional data (VSWT rankings). */
  shop_number?: string | null
}

export const getShopIdentity = () =>
  api.get<ShopIdentity>('/settings/shop-identity')

export const updateShopIdentity = (data: Partial<Omit<ShopIdentity, 'name' | 'business_address'>>) =>
  api.patch<ShopIdentity>('/settings/shop-identity', data)

// ── Customer Portal (public, no auth header) ──────────────────────────────────
export interface PortalLoyalty {
  tier_name: string
  tier_label: string
  points_balance: number
  points_dollar_value: number
  rolling_12m_spend_cents: number
}

export interface PortalIntakeJob {
  id: string
  customer_name: string
  job_address: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: string
  description?: string
  status: string
  created_at: string
}

export interface PortalProfile {
  customer_id: string
  name: string
  phone?: string
  email?: string
  intake_jobs: PortalIntakeJob[]
  loyalty?: PortalLoyalty
}

/** Texts a sign-in code to the phone; portalVerify exchanges it for a session. */
export const portalLookup = (slug: string, name: string, phone: string) =>
  api.post<{ sent: boolean; expires_minutes: number }>(`/public/portal/${slug}/lookup`, { name, phone })

export const portalVerify = (slug: string, phone: string, code: string) =>
  api.post<{ token: string; customer_id: string; name: string; phone?: string; email?: string }>(
    `/public/portal/${slug}/verify`,
    { phone, code },
  )

export const portalGetProfile = (slug: string, token: string) =>
  api.get<PortalProfile>(`/public/portal/${slug}/profile`, { params: { token } })

export const portalBook = (
  slug: string,
  token: string,
  data: {
    job_address: string
    vehicle_make?: string
    vehicle_model?: string
    vehicle_year?: string
    registration_plate?: string
    description?: string
    preferred_date?: string
  },
) => api.post<{ intake_job_id: string; status: string }>(`/public/portal/${slug}/book`, data, { params: { token } })

// ── Customer Orders ──────────────────────────────────────────────────────────

export type CustomerOrderStatus = 'to_order' | 'ordered' | 'arrived' | 'notified' | 'collected'

export interface CustomerOrder {
  id: string
  tenant_id: string
  customer_id: string | null
  customer_name: string | null
  title: string
  description: string | null
  supplier: string | null
  status: CustomerOrderStatus
  priority: string
  estimated_cost_cents: number
  notes: string | null
  created_at: string
  updated_at: string
}

export interface CustomerOrderCreatePayload {
  title: string
  description?: string
  supplier?: string
  customer_id?: string
  priority?: string
  estimated_cost_cents?: number
  notes?: string
}

export interface CustomerOrderUpdatePayload {
  title?: string
  description?: string
  supplier?: string
  customer_id?: string | null
  status?: CustomerOrderStatus
  priority?: string
  estimated_cost_cents?: number
  notes?: string
}

export const listCustomerOrders = (params?: { status?: string }) =>
  api.get<CustomerOrder[]>('/customer-orders', { params })

export const createCustomerOrder = (data: CustomerOrderCreatePayload) =>
  api.post<CustomerOrder>('/customer-orders', data)

export const updateCustomerOrder = (id: string, data: CustomerOrderUpdatePayload) =>
  api.patch<CustomerOrder>(`/customer-orders/${id}`, data)

export const deleteCustomerOrder = (id: string) =>
  api.delete(`/customer-orders/${id}`)

export interface CustomerOrderImportResult {
  dry_run: boolean
  total_rows: number
  imported: number
  skipped: number
  skipped_reasons: Record<string, number>
}

export const listCustomerOrderSheets = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<string[]>('/customer-orders/import/sheets', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const importCustomerOrders = (file: File, dryRun = true, sheetName?: string) => {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams({ dry_run: String(dryRun) })
  if (sheetName?.trim()) params.append('sheet_name', sheetName.trim())
  return api.post<CustomerOrderImportResult>(
    `/customer-orders/import?${params.toString()}`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 },
  )
}

// ── VSWT Regional Intelligence ──────────────────────────────────────────────────────────
// Weekly Mister Minit HQ regional export, parsed and shared, then ranked per logged-in shop.
// See backend/app/vswt_kpis.py for the KPI list/grouping this mirrors.

export type VswtKpiType = 'currency' | 'percent' | 'count' | 'ratio'
export type VswtKpiGroup =
  | 'Headline' | 'Budget & Last Year' | 'Conversion' | 'Category Sales'
  | 'Category Jobs' | 'Watch & Service Detail'

export interface VswtKpiDef {
  key: string
  label: string
  group: VswtKpiGroup
  type: VswtKpiType
}

export type VswtUnavailableReason = 'no_shop_number' | 'no_data' | 'shop_not_found'
export interface VswtUnavailable {
  available: false
  reason: VswtUnavailableReason
}

export interface VswtSummary {
  available: true
  shop_number: string
  shop_name: string | null
  area_name: string | null
  latest_week: number
  weeks_tracked: number
  region_size: number
  peer_size: number
  area_size: number
  sales: { value: number | null; prev_value: number | null; region_rank: number | null; prev_region_rank: number | null; peer_rank: number | null; area_rank: number | null }
  customers: { value: number | null; prev_value: number | null; region_rank: number | null; prev_region_rank: number | null }
  jobs: { value: number | null; prev_value: number | null; region_rank: number | null; prev_region_rank: number | null }
}
export const getVswtSummary = () => api.get<VswtSummary | VswtUnavailable>('/reports/vswt/summary')

export type VswtComparison = 'previous' | '4w' | '13w' | '52w' | 'last_year'
export interface VswtCockpitRow extends VswtKpiDef {
  current: number | null
  previous: number | null
  rolling_4: number | null
  rolling_13: number | null
  rolling_52: number | null
  rolling_counts: Record<string, number>
  last_year: number | null
  comparison: number | null
  delta: number | null
  delta_pct: number | null
  region_avg: number | null
  peer_avg: number | null
  rank: number | null
  previous_rank: number | null
  rank_change: number | null
  target: number | null
  target_variance: number | null
  zscore: number | null
  anomaly: 'high' | 'low' | null
  watch: 'high' | 'low' | null
  baseline_weeks: number
}
export interface VswtAnnotation {
  id: string
  week: number
  event_type: string
  note: string
  exclude_from_baselines: boolean
  created_at: string
  updated_at: string
}
export interface VswtAnomaly { key: string; label: string; direction: 'high' | 'low'; z: number; weeks: number; current: number | null }
export interface VswtAlert { severity: 'positive' | 'info' | 'warning' | 'critical'; title: string; message: string }
export interface VswtCockpit {
  available: true
  shop_number: string
  shop_name: string | null
  area_name: string | null
  viewing_own_shop: boolean
  week: number
  previous_week: number | null
  weeks: number[]
  comparison: VswtComparison
  region_size: number
  peer_size: number
  source: { filename: string | null; uploaded_at: string | null; shops_in_upload: number }
  rows: VswtCockpitRow[]
  drivers: {
    category_sales: { key: string; label: string; current: number | null; previous: number | null; delta: number | null; share_of_sales: number | null }[]
    sales_bridge: { total_change: number | null; customer_volume_effect: number | null; average_sale_effect: number | null }
  }
  alerts: VswtAlert[]
  anomalies: VswtAnomaly[]
  narrative: string
  annotations: VswtAnnotation[]
  region: { id: string; name: string; manager_name: string | null } | null
  region_annotations: RegionWeekAnnotation[]
  excluded_weeks: number[]
  targets: Record<string, number>
  email_weekly_report: boolean
  last_weekly_report_sent_at: string | null
}
export const getVswtCockpit = (params: { week?: number; comparison?: VswtComparison; shopNumber?: string } = {}) =>
  api.get<VswtCockpit | VswtUnavailable>('/reports/vswt/cockpit', {
    params: {
      ...(params.week ? { week: params.week } : {}),
      ...(params.comparison ? { comparison: params.comparison } : {}),
      ...(params.shopNumber ? { shop_number: params.shopNumber } : {}),
    },
  })

export interface VswtTargets { available: true; shop_number: string; targets: Record<string, number> }
export const getVswtTargets = () => api.get<VswtTargets | VswtUnavailable>('/reports/vswt/targets')
export const putVswtTargets = (targets: Record<string, number | null>) =>
  api.put<VswtTargets>('/reports/vswt/targets', { targets })

export interface VswtAnnotations { available: true; shop_number: string; annotations: VswtAnnotation[] }
export const getVswtAnnotations = () => api.get<VswtAnnotations | VswtUnavailable>('/reports/vswt/annotations')
export const putVswtAnnotation = (payload: { week: number; event_type: string; note: string; exclude_from_baselines?: boolean }) =>
  api.put<VswtAnnotation>('/reports/vswt/annotations', payload)
export const deleteVswtAnnotation = (id: string) => api.delete<{ deleted: string }>(`/reports/vswt/annotations/${id}`)

export interface VswtEmailPreference { enabled: boolean; last_sent_at: string | null }
export const getVswtEmailPreference = () => api.get<VswtEmailPreference>('/reports/vswt/email-preference')
export const putVswtEmailPreference = (enabled: boolean) => api.put<VswtEmailPreference>('/reports/vswt/email-preference', { enabled })
export const sendVswtEmailNow = () => api.post<{ sent: boolean }>('/reports/vswt/email-preference/send-now')

export interface VswtScorecardCell { value: number | null; rank: number | null }
export interface VswtScorecardWeekRow { week: number; region_size: number; cells: Record<string, VswtScorecardCell> }
export interface VswtScorecard {
  available: true
  shop_number: string
  shop_name: string | null
  area_name: string | null
  viewing_own_shop: boolean
  weeks: number[]
  groups: VswtKpiGroup[]
  kpis: VswtKpiDef[]
  matrix: VswtScorecardWeekRow[]
}
export const getVswtScorecard = (shopNumber?: string) =>
  api.get<VswtScorecard | VswtUnavailable>('/reports/vswt/scorecard', {
    params: shopNumber ? { shop_number: shopNumber } : undefined,
  })

export interface VswtRankingRow extends VswtKpiDef {
  value: number | null
  region_avg: number | null
  region_rank: number | null
  percentile: number | null
  peer_avg: number | null
  peer_rank: number | null
}
export interface VswtRankings {
  available: true
  shop_number: string
  shop_name: string | null
  area_name: string | null
  viewing_own_shop: boolean
  week: number
  weeks: number[]
  region_size: number
  peer_size: number
  rows: VswtRankingRow[]
}
export const getVswtRankings = (week?: number, shopNumber?: string) =>
  api.get<VswtRankings | VswtUnavailable>('/reports/vswt/rankings', {
    params: { ...(week ? { week } : {}), ...(shopNumber ? { shop_number: shopNumber } : {}) },
  })

export interface VswtShopReportWindow { value: number | null; rank: number | null }
export interface VswtShopReportMonthWindow extends VswtShopReportWindow { weeks_counted: number }
export interface VswtShopReportYearWindow extends VswtShopReportWindow {
  weeks_counted: number
  best_rank: number | null
  worst_rank: number | null
  rank_stdev: number | null
}
export interface VswtShopReportRow extends VswtKpiDef {
  week: VswtShopReportWindow
  month: VswtShopReportMonthWindow
  year: VswtShopReportYearWindow
}
export interface VswtShopReport {
  available: true
  shop_number: string
  shop_name: string | null
  area_name: string | null
  viewing_own_shop: boolean
  weeks_tracked: number
  region_size: number
  group: VswtKpiGroup
  groups: VswtKpiGroup[]
  kpis: VswtKpiDef[]
  rows: VswtShopReportRow[]
}
export const getVswtShopReport = (shopNumber?: string, group?: string) =>
  api.get<VswtShopReport | VswtUnavailable>('/reports/vswt/shop-report', {
    params: { ...(shopNumber ? { shop_number: shopNumber } : {}), ...(group ? { group } : {}) },
  })

// shop_number/shop_name are null for bottom-list entries that aren't the viewing shop —
// bottom performers are anonymized, only the viewer's own row (if it's down there) is named.
// weeks_counted is only present in Consistency mode (how many weeks the average rank is over).
export interface VswtLeaderboardEntry {
  rank: number; shop_number: string | null; shop_name: string | null; value: number | null
  is_me: boolean; weeks_counted?: number
}
export interface VswtLeaderboardBoard extends VswtKpiDef {
  top: VswtLeaderboardEntry[]
  bottom: VswtLeaderboardEntry[]
  my_rank: number | null
  total: number
}
export type VswtLeaderboardMode = 'latest' | 'consistency'
export interface VswtLeaderboards {
  available: true
  mode: VswtLeaderboardMode
  week: number
  weeks: number[]
  groups: ('All' | VswtKpiGroup)[]
  boards: VswtLeaderboardBoard[]
}
export const getVswtLeaderboards = (week?: number, group?: string, mode?: VswtLeaderboardMode) =>
  api.get<VswtLeaderboards | VswtUnavailable>('/reports/vswt/leaderboards', {
    params: { ...(week ? { week } : {}), ...(group ? { group } : {}), ...(mode ? { mode } : {}) },
  })

export interface VswtTrends {
  available: true
  shop_number: string
  shop_name: string | null
  area_name: string | null
  viewing_own_shop: boolean
  weeks: number[]
  latest_week: number
  sales_series: { week: number; shop: number | null; region_avg: number | null; peer_avg: number | null }[]
  customers_series: { week: number; shop: number | null; region_avg: number | null; peer_avg: number | null }[]
  jobs_series: { week: number; shop: number | null; region_avg: number | null; peer_avg: number | null }[]
  rank_series: { week: number; rank: number | null }[]
  category_series: { name: string; shop: number | null; region_avg: number | null }[]
  region_size: number
  annotations: VswtAnnotation[]
}
export const getVswtTrends = (weeksBack = 8, shopNumber?: string) =>
  api.get<VswtTrends | VswtUnavailable>('/reports/vswt/trends', {
    params: { weeks_back: weeksBack, ...(shopNumber ? { shop_number: shopNumber } : {}) },
  })

export interface VswtDirectoryRow {
  shop_number: string
  shop_name: string | null
  area_name: string | null
  store_format: string | null
  comp_status: string | null
  is_peer: boolean
  is_me: boolean
  values: Record<string, number | null>
}
export interface VswtDirectory {
  available: true
  week: number
  weeks: number[]
  region_size: number
  peer_size: number
  result_size: number
  group: VswtKpiGroup
  groups: VswtKpiGroup[]
  kpis: VswtKpiDef[]
  rows: VswtDirectoryRow[]
}
export const getVswtDirectory = (params: { week?: number; search?: string; group?: string; peerOnly?: boolean } = {}) =>
  api.get<VswtDirectory | VswtUnavailable>('/reports/vswt/directory', {
    params: {
      ...(params.week ? { week: params.week } : {}),
      ...(params.search ? { search: params.search } : {}),
      ...(params.group ? { group: params.group } : {}),
      ...(params.peerOnly ? { peer_only: true } : {}),
    },
  })

export interface VswtWeekSummary {
  week: number
  shop_count: number
  source_filenames: string[]
  uploaded_at: string | null
}
export const getVswtWeeks = () => api.get<{ weeks: VswtWeekSummary[] }>('/reports/vswt/weeks')
export const getVswtExportCsv = (params: { week?: number; shop_number?: string } = {}) =>
  api.get<Blob>('/reports/vswt/export', { params, responseType: 'blob' })
export const deleteVswtWeek = (week: number) => api.delete<{ deleted_week: number }>(`/reports/vswt/weeks/${week}`)

export interface VswtUploadBatchItem {
  filename: string
  internal_week: number | null
  week_number: number
  shop_count: number
  overwrite: boolean
  rows: Record<string, unknown>[]
}
export interface VswtUploadResult {
  failed_files: string[]
  batch: VswtUploadBatchItem[]
  existing_weeks: number[]
}
export const uploadVswtFiles = (files: File[]) => {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  return api.post<VswtUploadResult>('/reports/vswt/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

export interface VswtCommitFile { filename: string; week_number: number; rows: Record<string, unknown>[] }
export const commitVswtBatch = (batch: VswtCommitFile[]) =>
  api.post<{ saved: { week_number: number; shop_count: number }[] }>('/reports/vswt/commit', { batch })

// ── Weekly report builder ────────────────────────────────────────────────────────────────
// Hand-pick a handful of shops (e.g. your own franchisee group) and get one week's numbers for
// just those shops laid out together — for pasting into a group chat, not for browsing the region.

// Comprehensive by design: `values`/`ranks` cover every KPI across every group (not just
// Headline), keyed by VswtKpiDef.key — group them client-side via `kpis[].group` to render one
// section per group. `overall_avg_rank` is a single composite "how's this shop doing overall"
// number, averaged across every KPI that had a rank.
export interface VswtWeeklyReportShop {
  shop_number: string
  shop_name: string | null
  area_name: string | null
  is_me: boolean
  sales_value: number | null
  sales_rank: number | null
  customer_value: number | null
  jobs_value: number | null
  overall_avg_rank: number | null
  values: Record<string, number | null>
  ranks: Record<string, number | null>
}
export interface VswtWeeklyReportTotals {
  sales: number | null
  customers: number | null
  jobs: number | null
  avg_sales_rank: number | null
}
export interface VswtWeeklyReport {
  available: true
  week: number
  weeks: number[]
  region_size: number
  // When true, every rank in `shops[].ranks`/`sales_rank`/`overall_avg_rank` was computed only
  // against the other selected shops (rank_pool_size of them) — not the whole region.
  compare_within_selection: boolean
  rank_pool_size: number
  groups: VswtKpiGroup[]
  kpis: VswtKpiDef[]
  shops: VswtWeeklyReportShop[]
  missing_shop_numbers: string[]
  totals: VswtWeeklyReportTotals
}
export const getVswtWeeklyReport = (params: { week?: number; shopNumbers: string[]; compareWithinSelection?: boolean }) =>
  api.get<VswtWeeklyReport | VswtUnavailable>('/reports/vswt/weekly-report', {
    params: {
      ...(params.week ? { week: params.week } : {}),
      shop_numbers: params.shopNumbers.join(','),
      ...(params.compareWithinSelection ? { compare_within_selection: true } : {}),
    },
  })
export const getVswtWeeklyReportPdf = (params: { week?: number; shopNumbers: string[]; title?: string; compareWithinSelection?: boolean }) =>
  api.get<Blob>('/reports/vswt/weekly-report/pdf', {
    responseType: 'blob',
    params: {
      ...(params.week ? { week: params.week } : {}),
      shop_numbers: params.shopNumbers.join(','),
      ...(params.title ? { title: params.title } : {}),
      ...(params.compareWithinSelection ? { compare_within_selection: true } : {}),
    },
  })
