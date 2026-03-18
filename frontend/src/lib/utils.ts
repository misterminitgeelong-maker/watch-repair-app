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
  awaiting_quote:      'bg-[#EEE8F5] text-[#6A4A8B]',
  awaiting_go_ahead:   'bg-[#FEF0DC] text-[#9B6820]',
  go_ahead:            'bg-[#E8F0E4] text-[#3B6B42]',
  no_go:               'bg-[#F5E8E8] text-[#8B3A3A]',
  working_on:          'bg-[#E8EEF8] text-[#3A508B]',
  awaiting_parts:      'bg-[#FDECD3] text-[#9B4E0F]',
  parts_to_order:      'bg-[#F0EAF5] text-[#6B4A8B]',
  sent_to_labanda:     'bg-[#F0EBE0] text-[#6B5238]',
  quoted_by_labanda:   'bg-[#EAE0F0] text-[#5A3877]',
  service:             'bg-[#DFF0EC] text-[#2A6B65]',
  completed:           'bg-[#E4F0E4] text-[#2F6B34]',
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
