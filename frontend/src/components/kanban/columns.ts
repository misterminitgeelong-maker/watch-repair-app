export interface KanbanColumnDef<S extends string = string> {
  key: string
  label: string
  statuses: readonly S[]
  color: string
  bg: string
}

// One bar per real status point — no bundling. Legacy renamed statuses (kept only so
// pre-migration jobs stay visible) fold into the bar for their current equivalent.
export const WATCH_KANBAN_COLUMNS: readonly KanbanColumnDef[] = [
  {
    key: 'awaiting_quote',
    label: 'Awaiting Quote',
    statuses: ['awaiting_quote'],
    color: '#9A6E26',
    bg: '#F6EDD8',
  },
  {
    key: 'awaiting_customer_details',
    label: 'Awaiting Customer Details',
    statuses: ['awaiting_customer_details'],
    color: '#8A5A3B',
    bg: '#F5E9DE',
  },
  {
    key: 'quote_sent',
    label: 'Quote Sent',
    statuses: ['quote_sent'],
    color: '#2A5FA0',
    bg: '#EDF3FA',
  },
  {
    key: 'awaiting_go_ahead',
    label: 'Awaiting Go Ahead',
    statuses: ['awaiting_go_ahead'],
    color: '#3E6FB0',
    bg: '#E7F0FA',
  },
  {
    key: 'go_ahead',
    label: 'Go Ahead Given',
    statuses: ['go_ahead'],
    color: '#B06010',
    bg: '#FFF0E0',
  },
  {
    key: 'no_go',
    label: 'No Go',
    statuses: ['no_go'],
    color: '#B03A2A',
    bg: '#FBE7E3',
  },
  {
    key: 'at_third_party_for_quoting',
    label: 'At 3rd Party (Quoting)',
    // sent_to_labanda kept for legacy pre-migration jobs
    statuses: ['at_third_party_for_quoting', 'sent_to_labanda'],
    color: '#0F6B6B',
    bg: '#E3F2F2',
  },
  {
    key: 'third_party_quote_approved',
    label: '3rd Party Quote Approved',
    // quoted_by_labanda kept for legacy pre-migration jobs
    statuses: ['third_party_quote_approved', 'quoted_by_labanda'],
    color: '#127070',
    bg: '#E0F1F1',
  },
  {
    key: 'at_third_party_repairer',
    label: 'At 3rd Party Repairer',
    statuses: ['at_third_party_repairer'],
    color: '#186A6A',
    bg: '#DDEFEF',
  },
  {
    key: 'awaiting_parts',
    label: 'Awaiting Parts',
    // parts_to_order kept for legacy pre-migration jobs
    statuses: ['awaiting_parts', 'parts_to_order'],
    color: '#A0680F',
    bg: '#FBEBD3',
  },
  {
    key: 'working_on',
    label: 'In Work',
    // service kept for legacy pre-migration jobs
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
    key: 'awaiting_collection',
    label: 'Ready to Collect',
    statuses: ['awaiting_collection'],
    color: '#5A4A3B',
    bg: '#EEEBE5',
  },
  {
    key: 'collected',
    label: 'Collected',
    statuses: ['collected'],
    color: '#1A6A3A',
    bg: '#EBF8EF',
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
    key: 'booking_confirmed',
    label: 'Booking Confirmed',
    statuses: ['booking_confirmed', 'booked', 'pending_booking'],
    color: '#B06010',
    bg: '#FFF0E0',
  },
  {
    key: 'en_route',
    label: 'En Route',
    statuses: ['en_route', 'on_site'],
    color: '#6A3FC9',
    bg: '#EDE5F5',
  },
  {
    key: 'booking_on_hold',
    label: 'Booking on Hold',
    statuses: ['booking_on_hold', 'job_delayed'],
    color: '#A84F1A',
    bg: '#FDE8D8',
  },
  {
    key: 'booking_completed',
    label: 'Booking Completed',
    statuses: ['booking_completed', 'work_completed', 'invoice_paid'],
    color: '#1E7040',
    bg: '#E8F5ED',
  },
] as const

export const CUSTOMER_ORDER_KANBAN_COLUMNS: readonly KanbanColumnDef[] = [
  {
    key: 'to_order',
    label: 'To Order',
    statuses: ['to_order'],
    color: '#9A6E26',
    bg: '#F6EDD8',
  },
  {
    key: 'ordered',
    label: 'Ordered',
    statuses: ['ordered'],
    color: '#2A5FA0',
    bg: '#EDF3FA',
  },
  {
    key: 'arrived',
    label: 'Arrived',
    statuses: ['arrived'],
    color: '#6840B4',
    bg: '#F3EBF9',
  },
  {
    key: 'notified',
    label: 'Customer Notified',
    statuses: ['notified'],
    color: '#B06010',
    bg: '#FFF0E0',
  },
  {
    key: 'collected',
    label: 'Collected',
    statuses: ['collected'],
    color: '#1A6A3A',
    bg: '#EBF8EF',
  },
] as const

export function findColumnForStatus<T extends KanbanColumnDef>(
  columns: readonly T[],
  status: string,
): T | undefined {
  return columns.find(c => c.statuses.includes(status))
}
