import { http, HttpResponse } from 'msw'
import type { OpenApiAutoKeyJobRead } from '@/lib/generated/api-types'

/** Minimal GET /v1/auto-key-jobs fixture for contract / empty-list tests. */
export function makeMockAutoKeyJob(overrides: Partial<OpenApiAutoKeyJobRead> = {}): OpenApiAutoKeyJobRead {
  const base: OpenApiAutoKeyJobRead = {
    id: '00000000-0000-4000-8000-000000000001',
    tenant_id: '00000000-0000-4000-8000-000000000099',
    customer_id: '00000000-0000-4000-8000-000000000002',
    assigned_user_id: null,
    customer_account_id: null,
    job_number: 'AK-1001',
    status_token: 'tok',
    title: 'Mock job',
    description: null,
    vehicle_make: 'Toyota',
    vehicle_model: 'Camry',
    vehicle_year: 2020,
    registration_plate: 'MOCK1',
    vin: null,
    key_type: null,
    blade_code: null,
    chip_type: null,
    tech_notes: null,
    key_quantity: 1,
    programming_status: 'not_required',
    priority: 'normal',
    status: 'awaiting_quote',
    salesperson: null,
    collection_date: null,
    deposit_cents: 0,
    cost_cents: 0,
    created_at: '2026-04-01T00:00:00Z',
    scheduled_at: null,
    job_address: null,
    job_type: 'Lockout',
    visit_order: null,
    additional_services_json: null,
    commission_lead_source: 'shop_referred',
    customer_name: 'Test Customer',
    customer_phone: null,
  }
  return { ...base, ...overrides }
}

export const autoKeyJobsHandlers = [
  http.get('*/v1/auto-key-jobs', () => HttpResponse.json<OpenApiAutoKeyJobRead[]>([])),
]

export function autoKeyJobsHandlersWith(jobs: OpenApiAutoKeyJobRead[]) {
  return [http.get('*/v1/auto-key-jobs', () => HttpResponse.json(jobs))]
}
