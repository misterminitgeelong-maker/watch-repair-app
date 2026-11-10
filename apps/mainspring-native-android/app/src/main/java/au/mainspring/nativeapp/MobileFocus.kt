package au.mainspring.nativeapp

/** Same keys as backend mobile_cockpit.FOCUS_DEFINITIONS; the server applies the exact cockpit predicates. */
val MOBILE_FOCUS_OPTIONS = linkedMapOf(
    "late" to "Late", "today" to "Booked today", "in_field" to "In the field", "unscheduled" to "Unscheduled",
    "unassigned" to "Unassigned", "on_hold" to "On hold", "needs_quote" to "Needs a quote",
    "quote_follow_up" to "Quote follow-up", "confirmation_follow_up" to "Confirmation follow-up",
    "completed_unpaid" to "Completed, not paid", "overdue_invoices" to "Overdue invoices",
    "unpaid_invoices" to "Unpaid invoices", "this_week" to "Booked this week", "completed_this_week" to "Completed this week",
    "invoiced_this_week" to "Invoiced this week", "collected_this_week" to "Paid this week",
)
val MOBILE_REPORT_CATEGORIES = linkedMapOf("pipeline" to "Pipeline", "booking" to "Booking", "field" to "In the field", "completed" to "Completed", "paid" to "Paid", "lost" to "Lost")
