/**
 * Fixtures and MSW handlers for the three job-detail pages.
 *
 * The pages fan out to six to eight endpoints each — the job, its watch or shoe
 * or vehicle, the customer, attachments, quotes, work logs, users and customer
 * accounts. `onUnhandledRequest: 'error'` means every one has to be answered or
 * the test fails with an unrelated error, so they live here rather than being
 * restated in each test file.
 *
 * Builders take overrides so a test can say what it cares about — a status, a
 * price, an empty list — and inherit a plausible everything-else.
 */
import { http, HttpResponse } from 'msw'

export const API_BASE = 'http://127.0.0.1/v1'

export const JOB_ID = 'job-1'
export const WATCH_ID = 'watch-1'
export const SHOE_ID = 'shoe-1'
export const CUSTOMER_ID = 'cust-1'

type Overrides = Record<string, unknown>

export function makeCustomer(o: Overrides = {}) {
  return {
    id: CUSTOMER_ID,
    tenant_id: 'tenant-1',
    full_name: 'Marge Hooper',
    email: 'marge@example.com',
    phone: '0400 000 111',
    created_at: '2026-01-01T00:00:00Z',
    ...o,
  }
}

export function makeWatch(o: Overrides = {}) {
  return {
    id: WATCH_ID,
    tenant_id: 'tenant-1',
    customer_id: CUSTOMER_ID,
    brand: 'Omega',
    model: 'Seamaster',
    serial_number: 'SN-99',
    movement_type: 'automatic',
    created_at: '2026-01-01T00:00:00Z',
    ...o,
  }
}

export function makeRepairJob(o: Overrides = {}) {
  return {
    id: JOB_ID,
    tenant_id: 'tenant-1',
    watch_id: WATCH_ID,
    job_number: 'JOB-00042',
    status_token: 'tok-1',
    title: 'Full service',
    description: 'Runs fast by two minutes a day.',
    priority: 'normal',
    status: 'in_progress',
    deposit_cents: 5000,
    // The backend declares these with defaults, so a real response always
    // carries them. Omitting one here produced a "$NaN" that the API cannot
    // actually cause — a fixture less realistic than the contract.
    pre_quote_cents: 0,
    cost_cents: 42500,
    created_at: '2026-01-02T03:04:05Z',
    ...o,
  }
}

export function makeShoeJob(o: Overrides = {}) {
  return {
    id: JOB_ID,
    tenant_id: 'tenant-1',
    customer_id: CUSTOMER_ID,
    job_number: 'SHOE-00007',
    status_token: 'tok-2',
    title: 'Resole and stretch',
    status: 'in_progress',
    priority: 'normal',
    created_at: '2026-01-02T03:04:05Z',
    shoe: {
      id: SHOE_ID,
      tenant_id: 'tenant-1',
      customer_id: CUSTOMER_ID,
      brand: 'Loake',
      model: 'Chelsea',
      colour: 'Oxblood',
      created_at: '2026-01-01T00:00:00Z',
    },
    items: [],
    extra_shoes: [],
    ...o,
  }
}

export function makeAutoKeyJob(o: Overrides = {}) {
  return {
    id: JOB_ID,
    tenant_id: 'tenant-1',
    customer_id: CUSTOMER_ID,
    job_number: 'AK-00013',
    status_token: 'tok-3',
    title: 'Spare key cut and programmed',
    status: 'in_progress',
    priority: 'normal',
    key_quantity: 1,
    programming_status: 'pending',
    vehicle_make: 'Toyota',
    vehicle_model: 'HiLux',
    vehicle_year: 2019,
    registration_plate: 'ABC123',
    created_at: '2026-01-02T03:04:05Z',
    ...o,
  }
}

/** Every endpoint the three pages touch, with sensible empty defaults. */
export function jobDetailHandlers(opts: {
  repairJob?: Overrides | null
  shoeJob?: Overrides | null
  autoKeyJob?: Overrides | null
  watch?: Overrides
  customer?: Overrides
  attachments?: unknown[]
  quotes?: unknown[]
  workLogs?: unknown[]
  users?: unknown[]
  customerAccounts?: unknown[]
  jobStatus?: number
} = {}) {
  const status = opts.jobStatus ?? 200
  const fail = () => new HttpResponse(null, { status })

  return [
    http.get(`${API_BASE}/repair-jobs/:id`, () =>
      status !== 200 ? fail() : HttpResponse.json(opts.repairJob ?? makeRepairJob()),
    ),
    http.get(`${API_BASE}/shoe-repair-jobs/:id`, () =>
      status !== 200 ? fail() : HttpResponse.json(opts.shoeJob ?? makeShoeJob()),
    ),
    http.get(`${API_BASE}/auto-key-jobs/:id`, () =>
      status !== 200 ? fail() : HttpResponse.json(opts.autoKeyJob ?? makeAutoKeyJob()),
    ),
    http.get(`${API_BASE}/watches/:id`, () => HttpResponse.json(opts.watch ?? makeWatch())),
    http.get(`${API_BASE}/customers/:id`, () => HttpResponse.json(opts.customer ?? makeCustomer())),
    http.get(`${API_BASE}/attachments`, () => HttpResponse.json(opts.attachments ?? [])),
    http.get(`${API_BASE}/quotes`, () => HttpResponse.json(opts.quotes ?? [])),
    http.get(`${API_BASE}/work-logs`, () => HttpResponse.json(opts.workLogs ?? [])),
    http.get(`${API_BASE}/users`, () => HttpResponse.json(opts.users ?? [])),
    http.get(`${API_BASE}/customer-accounts`, () =>
      HttpResponse.json(opts.customerAccounts ?? []),
    ),
    // Catch-alls for the per-vertical extras (messages, history, specs, shoe
    // catalogue). A test that cares about one overrides it explicitly.
    http.get(`${API_BASE}/*`, () => HttpResponse.json([])),
  ]
}
