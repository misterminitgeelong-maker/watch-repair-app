package au.mainspring.nativeapp

/** Matches backend `JobStatus` literal for watch / shared workflow. */
val WATCH_JOB_STATUS_OPTIONS: List<String> = listOf(
    "awaiting_quote",
    "awaiting_go_ahead",
    "go_ahead",
    "no_go",
    "working_on",
    "awaiting_parts",
    "parts_to_order",
    "at_third_party_for_quoting",
    "third_party_quote_approved",
    "at_third_party_repairer",
    "sent_to_labanda",
    "quoted_by_labanda",
    "service",
    "completed",
    "awaiting_collection",
    "collected",
    "en_route",
    "on_site",
    "pending_booking",
    "booked",
    "awaiting_customer_details",
)

/** Superset for auto-key / mobile jobs (backend `JobStatus`). */
val AUTO_KEY_JOB_STATUS_OPTIONS: List<String> = (
    WATCH_JOB_STATUS_OPTIONS + listOf(
        "quote_sent",
        "awaiting_booking_confirmation",
        "booking_confirmed",
        "job_delayed",
        "work_completed",
        "invoice_paid",
        "failed_job",
    )
).distinct()

/** Watch status picker: same order as the web `JOB_STATUS_ORDER` (frontend/src/lib/utils.ts). */
val WATCH_PICKER_STATUSES: List<String> = listOf(
    "awaiting_quote", "awaiting_go_ahead", "go_ahead", "no_go",
    "at_third_party_for_quoting", "third_party_quote_approved", "at_third_party_repairer",
    "awaiting_parts", "working_on", "completed", "awaiting_collection", "collected",
)

private val WATCH_STATUS_LABEL_OVERRIDES = mapOf(
    "awaiting_quote" to "Awaiting Quote", "awaiting_customer_details" to "Awaiting customer details",
    "awaiting_go_ahead" to "Awaiting Go Ahead", "go_ahead" to "Go Ahead Given", "no_go" to "No Go",
    "working_on" to "Started Work", "awaiting_parts" to "Awaiting Parts", "parts_to_order" to "Parts Ordered",
    "sent_to_labanda" to "Sent to Labanda", "quoted_by_labanda" to "Quoted by Labanda",
    "at_third_party_for_quoting" to "At 3rd Party Repairer for Quoting",
    "third_party_quote_approved" to "3rd Party Repairer Approved Quote", "at_third_party_repairer" to "At 3rd Party Repairer",
    "service" to "Service", "completed" to "Work Completed", "awaiting_collection" to "Ready for Collection", "collected" to "Collected",
)

/** Label for a watch status; the third-party stages use the web wording. */
fun watchStatusLabel(status: String): String = WATCH_STATUS_LABEL_OVERRIDES[status] ?: au.mainspring.nativeapp.ui.statusLabel(status)

/** Statuses a job can be currently in but the picker does not offer (legacy / mobile), so the current one still shows. */
fun watchPickerOptions(current: String?): List<String> =
    if(current != null && current !in WATCH_PICKER_STATUSES) WATCH_PICKER_STATUSES + current else WATCH_PICKER_STATUSES
