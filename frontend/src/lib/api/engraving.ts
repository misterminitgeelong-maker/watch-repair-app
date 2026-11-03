import axios from 'axios'
import api, { withApiOrigin } from './client'

export type EngravingEventStatus = 'open' | 'paused' | 'closed'
export type EngravingOrderStatus = 'waiting' | 'engraving' | 'ready' | 'collected' | 'cancelled'
export type EngravingPlace = '1st' | '2nd' | '3rd' | 'Participant' | 'None'

export const ENGRAVING_PLACES: EngravingPlace[] = ['1st', '2nd', '3rd', 'Participant', 'None']

export interface EngravingEventStats {
  waiting: number
  engraving: number
  ready: number
  collected: number
  cancelled: number
  medals_total: number
  medals_remaining: number
  paid_cents: number
  unpaid_cents: number
}

export interface EngravingEvent {
  id: string
  name: string
  event_date: string | null
  location: string | null
  price_cents: number
  minutes_per_medal: number
  status: EngravingEventStatus
  sms_enabled: boolean
  public_token: string
  public_url: string
  created_at: string
  stats: EngravingEventStats
}

export interface EngravingOrder {
  id: string
  event_id: string
  order_number: string
  order_seq: number
  status_token: string
  athlete_name: string
  line2: string | null
  place: EngravingPlace
  qty: number
  medals_done: number
  phone: string | null
  status: EngravingOrderStatus
  paid: boolean
  paid_at: string | null
  amount_cents: number
  source: 'online' | 'walk_up'
  notes: string | null
  ready_at: string | null
  ready_sms_status: 'sent' | 'dry_run' | 'failed' | 'skipped' | null
  collected_at: string | null
  created_at: string
}

export interface EngravingQueue {
  event: EngravingEvent
  orders: EngravingOrder[]
}

export interface EngravingEventPayload {
  name: string
  event_date?: string | null
  location?: string | null
  price_cents?: number
  minutes_per_medal?: number
  sms_enabled?: boolean
}

export interface EngravingOrderPayload {
  athlete_name: string
  line2?: string | null
  place?: EngravingPlace
  qty?: number
  phone?: string | null
}

export interface EngravingOrderUpdatePayload extends Partial<EngravingOrderPayload> {
  paid?: boolean
  status?: EngravingOrderStatus
  notes?: string | null
}

export interface PublicEngravingEvent {
  name: string
  shop_name: string
  event_date: string | null
  location: string | null
  price_cents: number
  accepting_orders: boolean
  status: EngravingEventStatus
  wait_minutes: number
  medals_ahead: number
  name_max: number
  line2_max: number
  places: EngravingPlace[]
}

export interface PublicEngravingOrder {
  order_number: string
  status_token: string
  event_name: string
  shop_name: string
  athlete_name: string
  line2: string | null
  place: EngravingPlace
  qty: number
  medals_done: number
  status: EngravingOrderStatus
  paid: boolean
  amount_cents: number
  queue_position: number | null
  wait_minutes: number | null
  phone_masked: string | null
  created_at: string
  ready_at: string | null
}

// ── Operator ────────────────────────────────────────────────────────────────

export const listEngravingEvents = () => api.get<EngravingEvent[]>('/engraving/events')

export const createEngravingEvent = (data: EngravingEventPayload) =>
  api.post<EngravingEvent>('/engraving/events', data)

export const updateEngravingEvent = (id: string, data: Partial<EngravingEventPayload> & { status?: EngravingEventStatus }) =>
  api.patch<EngravingEvent>(`/engraving/events/${id}`, data)

export const getEngravingQueue = (eventId: string) =>
  api.get<EngravingQueue>(`/engraving/events/${eventId}/queue`)

export const createWalkUpEngravingOrder = (eventId: string, data: EngravingOrderPayload & { paid?: boolean; notes?: string | null }) =>
  api.post<EngravingOrder>(`/engraving/events/${eventId}/orders`, data)

export const updateEngravingOrder = (orderId: string, data: EngravingOrderUpdatePayload) =>
  api.patch<EngravingOrder>(`/engraving/orders/${orderId}`, data)

export const startEngravingOrder = (orderId: string) =>
  api.post<EngravingOrder>(`/engraving/orders/${orderId}/start`)

export const engravingMedalDone = (orderId: string) =>
  api.post<EngravingOrder>(`/engraving/orders/${orderId}/medal-done`)

export const resendEngravingReady = (orderId: string) =>
  api.post<EngravingOrder>(`/engraving/orders/${orderId}/resend-ready`)

export type LaserSoftware = 'xtool' | 'lightburn' | 'ezcad2' | 'csv'
export const LASER_SOFTWARE: { value: LaserSoftware; label: string; ext: string }[] = [
  { value: 'xtool', label: 'xTool', ext: 'csv' },
  { value: 'lightburn', label: 'LightBurn', ext: 'csv' },
  { value: 'ezcad2', label: 'EZCad2', ext: 'zip' },
  { value: 'csv', label: 'Plain CSV', ext: 'csv' },
]

export const exportEngravingFile = (eventId: string, software: LaserSoftware, limit?: number) =>
  api.get<Blob>(`/engraving/events/${eventId}/export`, { params: { software, ...(limit ? { limit } : {}) }, responseType: 'blob' })

export const exportEngravingCsv = (eventId: string, paidOnly = false) =>
  api.get<Blob>(`/engraving/events/${eventId}/export.csv`, { params: { paid_only: paidOnly }, responseType: 'blob' })

// ── Public (parents) ────────────────────────────────────────────────────────

export const getPublicEngravingEvent = (token: string) =>
  axios.get<PublicEngravingEvent>(withApiOrigin(`/v1/public/engraving/events/${token}`))

export const createPublicEngravingOrder = (token: string, data: EngravingOrderPayload) =>
  axios.post<PublicEngravingOrder>(withApiOrigin(`/v1/public/engraving/events/${token}/orders`), data)

export const getPublicEngravingOrder = (statusToken: string) =>
  axios.get<PublicEngravingOrder>(withApiOrigin(`/v1/public/engraving/orders/${statusToken}`))

// ── Display helpers ─────────────────────────────────────────────────────────

export function engravingPlaceText(place: EngravingPlace | string): string {
  if (place === 'None' || !place) return ''
  if (place === 'Participant') return 'Participant'
  return `${place} Place`
}

/** Font size (px) that keeps a name inside the medal preview. */
export function medalNameSize(name: string, base = 30): number {
  const len = name.trim().length
  if (len <= 10) return base
  if (len <= 14) return Math.round(base * 0.86)
  if (len <= 18) return Math.round(base * 0.72)
  return Math.round(base * 0.6)
}
