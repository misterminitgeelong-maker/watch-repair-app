package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.AutoKeyJobRead
import au.mainspring.nativeapp.api.canonicalMobileStatus

/** Pure rules for the mobile Today run sheet (web MobileTodayWorkspace + dispatchHelpers.nextMobileStatus). */

/** Next forward status for a one-tap action, or null when the job needs the full detail screen. */
fun nextMobileStatus(status: String): String? = when(canonicalMobileStatus(status)) {
    "awaiting_quote" -> "quote_sent"
    "quote_sent" -> "awaiting_booking_confirmation"
    "awaiting_booking_confirmation" -> "booking_confirmed"
    "booking_confirmed" -> "en_route"
    "en_route" -> "on_site"
    "on_site" -> "work_completed"
    else -> null
}

fun quickStatusCopy(status: String): String = when(status) {
    "en_route" -> "Start trip"
    "on_site" -> "I’ve arrived"
    "work_completed" -> "Complete job"
    else -> "Mark " + au.mainspring.nativeapp.ui.statusLabel(status)
}

/** Completing work can create an invoice and message the customer, so it always asks first. */
fun needsCompletionConfirm(target: String) = target == "work_completed"

private val FIELD_STATUSES = setOf("en_route", "on_site", "working_on", "service")

/** Jobs already out in the field first, then by booked time; unscheduled last (web jobSort). */
fun runSheetOrder(jobs: List<AutoKeyJobRead>): List<AutoKeyJobRead> =
    jobs.sortedWith(compareByDescending<AutoKeyJobRead> { it.status in FIELD_STATUSES }.thenBy { bookingInstant(it.scheduledAt) ?: java.time.Instant.MAX })

/** Late + in-the-field + booked-today, de-duplicated by id and ordered for the day. */
fun mergeRunSheet(late: List<AutoKeyJobRead>, inField: List<AutoKeyJobRead>, today: List<AutoKeyJobRead>): List<AutoKeyJobRead> =
    runSheetOrder((late + inField + today).distinctBy { it.id })

/** Needs-action queues shown above the run sheet, in web order. */
val NEEDS_ACTION_QUEUES: List<Pair<String, String>> = listOf(
    "late" to "Late", "unassigned" to "Unassigned", "unscheduled" to "Unscheduled", "on_hold" to "On hold",
)

/** Digits and a leading plus only, ready for a tel: URI. Blank when there is nothing dialable. */
fun dialDigits(phone: String?): String = phone.orEmpty().filter { it.isDigit() || it == '+' }

/** Google Maps turn-by-turn directions to the job address, or null when there is no address. */
fun directionsUri(address: String?): String? = address?.trim()?.takeIf { it.isNotEmpty() }?.let {
    "https://www.google.com/maps/dir/?api=1&destination=" + java.net.URLEncoder.encode(it, "UTF-8").replace("+", "%20")
}

/** One-line summary of the badge numbers: "N action flags". */
fun attentionTotal(counts: Map<String, Int>): Int = NEEDS_ACTION_QUEUES.sumOf { counts[it.first] ?: 0 }
