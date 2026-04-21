export interface KanbanColumnDef<S extends string = string> {
  key: string
  label: string
  statuses: readonly S[]
  color: string
  bg: string
}

export const WATCH_KANBAN_COLUMNS: readonly KanbanColumnDef[] = [
  {
    key: 'quote',
    label: 'Quote Needed',
    statuses: ['awaiting_quote', 'awaiting_customer_details'],
    color: '#9A6E26',
    bg: '#F6EDD8',
  },
  {
    key: 'approval',
    label: 'Awaiting Approval',
    statuses: ['awaiting_go_ahead', 'quote_sent'],
    color: '#2A5FA0',
    bg: '#EDF3FA',
  },
  {
    key: 'approved',
    label: 'Approved',
    statuses: ['go_ahead', 'awaiting_parts', 'parts_to_order', 'sent_to_labanda', 'quoted_by_labanda'],
    color: '#B06010',
    bg: '#FFF0E0',
  },
  {
    key: 'in_work',
    label: 'In Work',
    statuses: ['working_on', 'service'],
    color: '#6840B4',
    bg: '#F3EBF9',
  },
  {
    key: 'completed',
    label: 'Completed',
    statuses: ['completed'],
    color: '#1A6A3A',
    bg: '#EBF8EF',
  },
  {
    key: 'collect',
    label: 'Ready to Collect',
    statuses: ['awaiting_collection', 'collected'],
    color: '#5A4A3B',
    bg: '#EEEBE5',
  },
] as const

export const SHOE_KANBAN_COLUMNS: readonly KanbanColumnDef[] = [
  {
    key: 'quote',
    label: 'Quote Needed',
    statuses: ['awaiting_quote', 'awaiting_customer_details'],
    color: '#9A6E26',
    bg: '#F6EDD8',
  },
  {
    key: 'approval',
    label: 'Awaiting Approval',
    statuses: ['awaiting_go_ahead', 'quote_sent'],
    color: '#2A5FA0',
    bg: '#EDF3FA',
  },
  {
    key: 'in_work',
    label: 'In Work',
    statuses: ['go_ahead', 'awaiting_parts', 'parts_to_order', 'working_on', 'service'],
    color: '#6840B4',
    bg: '#F3EBF9',
  },
  {
    key: 'collect',
    label: 'Ready to Collect',
    statuses: ['completed', 'awaiting_collection', 'collected'],
    color: '#1A6A3A',
    bg: '#EBF8EF',
  },
] as const

export const AUTO_KEY_KANBAN_COLUMNS: readonly KanbanColumnDef[] = [
  {
    key: 'awaiting_quote',
    label: 'Awaiting Quote',
    statuses: ['awaiting_quote', 'awaiting_customer_details'],
    color: '#C07820',
    bg: '#FAEEDB',
  },
  {
    key: 'quote_sent',
    label: 'Quote Sent',
    statuses: ['quote_sent', 'awaiting_booking_confirmation'],
    color: '#2A5FA0',
    bg: '#EDF3FA',
  },
  {
    key: 'booked',
    label: 'Booking Confirmed',
    statuses: ['booking_confirmed', 'booked', 'pending_booking'],
    color: '#B06010',
    bg: '#FFF0E0',
  },
  {
    key: 'dispatch',
    label: 'En Route / On Site',
    statuses: ['en_route', 'on_site', 'working_on'],
    color: '#C96A5A',
    bg: '#FBEAE6',
  },
  {
    key: 'complete',
    label: 'Work Completed',
    statuses: ['work_completed', 'completed', 'invoice_paid'],
    color: '#1E7040',
    bg: '#E8F5ED',
  },
] as const

export function findColumnForStatus<T extends KanbanColumnDef>(
  columns: readonly T[],
  status: string,
): T | undefined {
  return columns.find(c => c.statuses.includes(status))
}
