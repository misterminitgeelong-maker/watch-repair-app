import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCents(cents: number, currency = 'USD') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(cents / 100)
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit', hour12: false })
}

/** Format estimated turnaround for shoe repairs: "3–5 days" or "~3 days" */
export function formatEstimatedTurnaround(min: number, max: number): string {
  if (min === max) return `~${min} day${min === 1 ? '' : 's'}`
  return `${min}–${max} days`
}

export const COMPLEXITY_LABELS: Record<string, string> = {
  simple: 'Simple',
  standard: 'Standard',
  complex: 'Complex',
}

// Single source of truth for job status order (watch repair directory views)
export const JOB_STATUS_ORDER = [
  'awaiting_quote',
  'awaiting_go_ahead',
  'go_ahead',
  'no_go',
  'parts_to_order',
  'sent_to_labanda',
  'quoted_by_labanda',
  'awaiting_parts',
  'working_on',
  'service',
  'completed',
  'awaiting_collection',
  'collected',
] as const

export const ACTIVE_DIRECTORY_STATUSES = [
  'awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'parts_to_order', 'sent_to_labanda',
  'quoted_by_labanda', 'awaiting_parts', 'working_on', 'service',
] as const

export const CLOSED_DIRECTORY_STATUSES = ['no_go', 'completed', 'awaiting_collection', 'collected'] as const

export const STATUS_LABELS: Record<string, string> = {
  awaiting_quote:      'Awaiting Quote',
  awaiting_go_ahead:   'Awaiting Go Ahead',
  go_ahead:            'Go Ahead Given',
  no_go:               'No Go',
  working_on:          'Started Work',
  awaiting_parts:      'Awaiting Parts',
  parts_to_order:      'Parts Ordered',
  sent_to_labanda:     'Sent to Labanda',
  quoted_by_labanda:   'Quoted by Labanda',
  service:             'Service',
  completed:           'Work Completed',
  awaiting_collection: 'Ready for Collection',
  collected:           'Collected',
  en_route:            'En Route',
  on_site:             'On Site',
  pending_booking:     'Awaiting booking confirm',
  booked:              'Confirmed booking',
  draft:               'Draft',
  sent:                'Sent',
  approved:            'Approved',
  declined:            'Declined',
  expired:             'Expired',
  unpaid:              'Unpaid',
  paid:                'Paid',
  void:                'Void',
}

export const STATUS_COLORS: Record<string, string> = {
  // Mobile Services dispatch palette (grey, amber, blue, orange, purple, green, red, dark green)
  awaiting_quote:      'bg-[#E8E6E3] text-[#6B5D52]',
  awaiting_go_ahead:   'bg-[#FEF0DC] text-[#9B6820]',
  go_ahead:            'bg-[#E0E8F5] text-[#2E4A7A]',
  no_go:               'bg-[#F5E8E8] text-[#8B3A3A]',
  working_on:          'bg-[#FDF0E6] text-[#B35A1F]',
  en_route:            'bg-[#EDE5F5] text-[#5D4A9B]',
  on_site:             'bg-[#E4F0E4] text-[#2F6A3D]',
  pending_booking:     'bg-[#FFF4E0] text-[#B86B00]',
  booked:              'bg-[#E0E8F5] text-[#2E4A7A]',
  awaiting_parts:      'bg-[#FDE8E8] text-[#A53A3A]',
  parts_to_order:      'bg-[#F0EAF5] text-[#6B4A8B]',
  sent_to_labanda:     'bg-[#F0EBE0] text-[#6B5238]',
  quoted_by_labanda:   'bg-[#EAE0F0] text-[#5A3877]',
  service:             'bg-[#DFF0EC] text-[#2A6B65]',
  completed:           'bg-[#D4E8D4] text-[#1F5C24]',
  awaiting_collection: 'bg-[#FEF0DC] text-[#9B6820]',
  collected:           'bg-[#DFF0EC] text-[#2A6B65]',
  draft:               'bg-[#EEEBE5] text-[#7A6A5A]',
  sent:                'bg-[#E8EEF8] text-[#3A508B]',
  approved:            'bg-[#E4F0E4] text-[#2F6B34]',
  declined:            'bg-[#F5E8E8] text-[#8B3A3A]',
  expired:             'bg-[#EEEBE5] text-[#9B8A7A]',
  unpaid:              'bg-[#FDECD3] text-[#9B4E0F]',
  paid:                'bg-[#E4F0E4] text-[#2F6B34]',
  void:                'bg-[#EEEBE5] text-[#9B9080]',
}
