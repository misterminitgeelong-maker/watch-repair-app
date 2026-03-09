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

export const STATUS_LABELS: Record<string, string> = {
  intake: 'Intake',
  diagnosis: 'Diagnosis',
  awaiting_approval: 'Awaiting Approval',
  in_repair: 'In Repair',
  qc: 'QC',
  ready: 'Ready',
  delivered: 'Delivered',
  cancelled: 'Cancelled',
  draft: 'Draft',
  sent: 'Sent',
  approved: 'Approved',
  declined: 'Declined',
  expired: 'Expired',
  unpaid: 'Unpaid',
  paid: 'Paid',
  void: 'Void',
}

export const STATUS_COLORS: Record<string, string> = {
  intake:            'bg-[#F0EBE0] text-[#6B5238]',
  diagnosis:         'bg-[#FEF0DC] text-[#9B6820]',
  awaiting_approval: 'bg-[#FDECD3] text-[#9B4E0F]',
  in_repair:         'bg-[#E8F0E4] text-[#3B6B42]',
  qc:                'bg-[#F0EAF5] text-[#6B4A8B]',
  ready:             'bg-[#E4F0E4] text-[#2F6B34]',
  delivered:         'bg-[#DFF0EC] text-[#2A6B65]',
  cancelled:         'bg-[#F5E8E8] text-[#8B3A3A]',
  draft:             'bg-[#EEEBE5] text-[#7A6A5A]',
  sent:              'bg-[#E8EEF8] text-[#3A508B]',
  approved:          'bg-[#E4F0E4] text-[#2F6B34]',
  declined:          'bg-[#F5E8E8] text-[#8B3A3A]',
  expired:           'bg-[#EEEBE5] text-[#9B8A7A]',
  unpaid:            'bg-[#FDECD3] text-[#9B4E0F]',
  paid:              'bg-[#E4F0E4] text-[#2F6B34]',
  void:              'bg-[#EEEBE5] text-[#9B9080]',
}
