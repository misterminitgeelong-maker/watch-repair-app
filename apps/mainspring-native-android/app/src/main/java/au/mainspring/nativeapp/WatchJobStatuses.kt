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
