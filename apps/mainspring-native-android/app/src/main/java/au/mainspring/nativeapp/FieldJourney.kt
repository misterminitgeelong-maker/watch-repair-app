package au.mainspring.nativeapp

/** A suggestion only: every write still goes through the versioned status workflow. */
data class FieldJourney(val step: Int, val title: String, val guidance: String, val action: String, val targetStatus: String? = null)
fun fieldJourney(status: String): FieldJourney = when(status) {
    "booked", "booking_confirmed" -> FieldJourney(0, "Ready to head out", "Check the vehicle, address and required equipment before leaving.", "Mark En Route", "en_route")
    "en_route" -> FieldJourney(1, "On the way", "Navigate to the customer. Mark arrival when you reach the site.", "Mark on site", "on_site")
    "on_site", "working_on", "service", "go_ahead" -> FieldJourney(2, "At the job", "Review the quote and customer approval before carrying out the work.", "Quote & approval")
    "work_completed", "completed", "awaiting_collection" -> FieldJourney(3, "Work complete", "Review the invoice and record payment after receiving it.", "Review invoice & payment")
    "invoice_paid", "collected" -> FieldJourney(4, "Job wrapped up", "Check the payment record and keep the job documents together.", "View documents")
    "awaiting_quote", "quote_sent", "awaiting_go_ahead", "quoted_by_labanda" -> FieldJourney(-1, "Quote & approval", "Confirm the scope, price and customer approval before booking the work.", "Review quote")
    else -> FieldJourney(-1, "Review this job", "Check the booking and current status before taking the next step.", "Review documents")
}

/** Keep work already underway ahead of untouched bookings; ties retain schedule order. */
fun nextFieldJob(jobs: List<au.mainspring.nativeapp.api.AutoKeyJobRead>) =
    jobs.firstOrNull { it.status in setOf("on_site", "working_on", "service") }
        ?: jobs.firstOrNull { it.status == "en_route" }
        ?: jobs.firstOrNull { it.status in setOf("booked", "booking_confirmed") }
        ?: jobs.firstOrNull()
