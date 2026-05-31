import { STATUS_LABELS } from '@/lib/utils'
import type { CustomerPortalJob } from '@/lib/api'

export type PortalStage = 'received' | 'in_progress' | 'ready' | 'collected'

const WATCH_STAGE: Record<string, PortalStage> = {
  awaiting_go_ahead: 'received',
  awaiting_quote: 'received',
  no_go: 'collected',
  go_ahead: 'in_progress',
  working_on: 'in_progress',
  awaiting_parts: 'in_progress',
  parts_to_order: 'in_progress',
  sent_to_labanda: 'in_progress',
  quoted_by_labanda: 'in_progress',
  service: 'in_progress',
  completed: 'ready',
  awaiting_collection: 'ready',
  collected: 'collected',
  cancelled: 'collected',
}

const SHOE_STAGE: Record<string, PortalStage> = {
  awaiting_go_ahead: 'received',
  awaiting_quote: 'received',
  no_go: 'collected',
  go_ahead: 'in_progress',
  working_on: 'in_progress',
  awaiting_parts: 'in_progress',
  completed: 'ready',
  awaiting_collection: 'ready',
  collected: 'collected',
}

const AUTO_KEY_STAGE: Record<string, PortalStage> = {
  awaiting_customer_details: 'received',
  awaiting_quote: 'received',
  quote_sent: 'received',
  pending_booking: 'received',
  booking_confirmed: 'in_progress',
  booked: 'in_progress',
  en_route: 'in_progress',
  on_site: 'in_progress',
  job_delayed: 'in_progress',
  work_completed: 'ready',
  awaiting_collection: 'ready',
  booking_completed: 'collected',
  invoice_paid: 'collected',
  failed_job: 'collected',
  cancelled: 'collected',
}

const STAGE_LABELS: Record<PortalStage, string> = {
  received: 'Received',
  in_progress: 'In progress',
  ready: 'Ready',
  collected: 'Collected',
}

const STAGE_ORDER: PortalStage[] = ['received', 'in_progress', 'ready', 'collected']

export function portalJobStage(type: CustomerPortalJob['type'], status: string): PortalStage {
  const map =
    type === 'watch' ? WATCH_STAGE : type === 'shoe' ? SHOE_STAGE : AUTO_KEY_STAGE
  return map[status] ?? 'in_progress'
}

export function portalJobStatusLabel(_type: CustomerPortalJob['type'], status: string): string {
  return STATUS_LABELS[status] ?? status.replace(/_/g, ' ')
}

export function portalStageLabel(stage: PortalStage): string {
  return STAGE_LABELS[stage]
}

export function portalStageIndex(stage: PortalStage): number {
  return STAGE_ORDER.indexOf(stage)
}

export { STAGE_ORDER }
