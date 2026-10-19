package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.AutoKeyJobRead
import java.time.Instant

/** Dispatch SLA chips, mirroring the web `computeSlaChip` (frontend/src/pages/autoKey/dispatchHelpers.ts). */
enum class SlaKind(val label: String, val weight: Int) { LATE("Late", 3), AT_RISK("At risk", 2), AGING("Unscheduled aging", 1) }

private val SLA_STOP_CLOCK = setOf("en_route", "on_site", "working_on", "service")
private val SLA_CLOSED = setOf("work_completed", "completed", "booking_completed", "awaiting_collection", "collected", "invoice_paid", "paid",
    "lost", "cancelled", "no_go", "failed_job", "declined")
private const val AT_RISK_MINUTES = 30L
private const val AGING_HOURS = 24L

fun slaChip(job: AutoKeyJobRead, now: Instant = Instant.now()): SlaKind? {
    if(job.status in SLA_STOP_CLOCK || job.status in SLA_CLOSED) return null
    val scheduled = job.scheduledAt
    if(scheduled != null) {
        val at = bookingInstant(scheduled) ?: return null
        return when {
            at.isBefore(now) -> SlaKind.LATE
            !at.isAfter(now.plusSeconds(AT_RISK_MINUTES * 60)) -> SlaKind.AT_RISK
            else -> null
        }
    }
    val created = bookingInstant(job.createdAt) ?: return null
    return if(!created.isAfter(now.minusSeconds(AGING_HOURS * 3600))) SlaKind.AGING else null
}

/** Order by saved visit_order first, then booking time (web `compareByVisitThenTime`). */
fun compareByVisitThenTime(a: AutoKeyJobRead, b: AutoKeyJobRead): Int {
    val va = a.visitOrder; val vb = b.visitOrder
    if(va != null && vb != null && va != vb) return va - vb
    if(va != null && vb == null) return -1
    if(va == null && vb != null) return 1
    return (bookingInstant(a.scheduledAt) ?: Instant.EPOCH).compareTo(bookingInstant(b.scheduledAt) ?: Instant.EPOCH)
}

val DispatchSlaOrder: Comparator<AutoKeyJobRead> = Comparator { a, b -> compareByVisitThenTime(a, b) }
