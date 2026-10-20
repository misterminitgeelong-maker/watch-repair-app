package au.mainspring.nativeapp

import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset

/**
 * Pure logic shared by the watch and shoe lanes of the repair queue. It mirrors the web
 * `RepairQueueModal`: the same urgency / priority / age ordering, the same saved-order merge,
 * the same filters and the same note chips, so the day's progress means the same on both apps.
 */

/** The fields of a job the queue needs, lane-agnostic. */
data class QueueRow(val id: String, val status: String, val priority: String, val collectionDate: String?, val createdAt: String?)

/** Per-shop-day counters saved with the day state (`advanced`, `checkedIn`, `skipped`). */
data class QueueDayStats(val advanced: Int = 0, val checkedIn: Int = 0, val skipped: Int = 0)

/** Queue filters; an empty set means "any". */
data class QueueFilters(
    val statuses: Set<String> = emptySet(),
    val priorities: Set<String> = emptySet(),
    val dueTodayOnly: Boolean = false,
) {
    /** Number of active filters, shown on the Filter button (web `filterCount`). */
    val count: Int get() = statuses.size + priorities.size + if (dueTodayOnly) 1 else 0
    val active: Boolean get() = count > 0
}

val QUEUE_PRIORITIES: List<String> = listOf("urgent", "high", "normal", "low")
private val PRIORITY_ORDER: Map<String, Int> = QUEUE_PRIORITIES.withIndex().associate { it.value to it.index }

/** Statuses offered as filter chips (web `QUEUE_STATUSES`). */
val QUEUE_FILTER_STATUSES: List<String> = listOf("awaiting_quote", "awaiting_go_ahead", "go_ahead", "working_on", "completed", "awaiting_collection")

/** Statuses where a "remind customer" SMS makes sense (web `SMS_REMIND_STATUSES`). */
val QUEUE_SMS_REMIND_STATUSES: Set<String> = setOf("awaiting_go_ahead", "completed", "awaiting_collection")

val QUEUE_ADVANCE_NOTE_CHIPS: Map<String, List<String>> = mapOf(
    "awaiting_go_ahead" to listOf("Called customer", "Left voicemail", "Sent SMS", "Emailed customer"),
    "go_ahead" to listOf("Confirmed by phone", "Confirmed by SMS", "Customer came in"),
    "working_on" to listOf("Parts sourced", "Started service", "Battery replaced", "Crystal replaced"),
    "completed" to listOf("Service complete", "Pressure tested", "Timekeeping checked"),
    "awaiting_collection" to listOf("Customer notified", "SMS sent", "Called customer"),
    "collected" to listOf("Customer collected", "Shipped to customer"),
)

val QUEUE_STATUS_NOTE_CHIPS: Map<String, List<String>> = mapOf(
    "awaiting_quote" to listOf("Needs parts assessment", "Complex movement", "Awaiting supplier quote", "Rush job"),
    "awaiting_go_ahead" to listOf("Called - no answer", "SMS sent", "Quote expires soon", "Customer reconsidering"),
    "go_ahead" to listOf("Parts ordered", "Sourcing parts", "Waiting on delivery"),
    "working_on" to listOf("Waiting on parts", "Movement stripped", "Parts arrived", "Extra time needed"),
    "completed" to listOf("Invoice ready", "Tested and passed"),
    "awaiting_collection" to listOf("Reminder sent", "Left message"),
)

val QUEUE_NO_UPDATE_CHIPS: Map<String, List<String>> = mapOf(
    "awaiting_quote" to listOf("Still assessing", "Awaiting parts price", "Complex job - more time needed"),
    "awaiting_go_ahead" to listOf("Waiting on customer", "Customer not responding", "Quote sent - awaiting reply"),
    "go_ahead" to listOf("Parts not arrived yet", "Waiting on supplier", "Backlogged"),
    "working_on" to listOf("Waiting on parts", "Still in progress", "Waiting on tools"),
    "completed" to listOf("Awaiting customer collection", "Will notify shortly"),
    "awaiting_collection" to listOf("Customer unavailable", "Will call again"),
)

val QUEUE_RECOMMENDED_ACTION: Map<String, String> = mapOf(
    "awaiting_quote" to "Write up a quote",
    "awaiting_go_ahead" to "Waiting on customer approval",
    "go_ahead" to "Ready to start - begin work",
    "working_on" to "In progress - continue work",
    "completed" to "Notify customer for collection",
    "awaiting_collection" to "Waiting at counter for pickup",
)

/** Default note when a card is marked "No update" without a reason (web `handleCheckedIn`). */
const val QUEUE_DEFAULT_CHECKED_IN_NOTE = "Checked in - no update"

private fun datePart(value: String?): LocalDate? =
    value?.trim()?.takeIf { it.length >= 10 }?.let { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() }

/** 0 overdue, 1 due today, 2 due tomorrow, 3 later or no date (web `getCollectionUrgency`). */
fun collectionUrgency(collectionDate: String?, today: LocalDate = LocalDate.now()): Int {
    val d = datePart(collectionDate) ?: return 3
    return when {
        d.isBefore(today) -> 0
        d == today -> 1
        d == today.plusDays(1) -> 2
        else -> 3
    }
}

/** Best-effort epoch milliseconds for the timestamp shapes the API returns; 0 when unreadable. */
fun queueEpochMillis(value: String?): Long {
    val v = value?.trim().orEmpty()
    if (v.isEmpty()) return 0L
    return runCatching { Instant.parse(v).toEpochMilli() }.getOrNull()
        ?: runCatching { OffsetDateTime.parse(v).toInstant().toEpochMilli() }.getOrNull()
        ?: runCatching { LocalDateTime.parse(v).toInstant(ZoneOffset.UTC).toEpochMilli() }.getOrNull()
        ?: runCatching { LocalDate.parse(v.take(10)).atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli() }.getOrNull()
        ?: 0L
}

/** Queue order: collection urgency, then priority, then oldest first (web `sortQueue`), ties by due date and number. */
fun sortQueueRows(rows: List<QueueRow>, today: LocalDate = LocalDate.now()): List<QueueRow> = rows.sortedWith(
    compareBy<QueueRow> { collectionUrgency(it.collectionDate, today) }
        .thenBy { PRIORITY_ORDER[it.priority] ?: 99 }
        .thenBy { queueEpochMillis(it.createdAt) }
        .thenBy { it.collectionDate.orEmpty() },
)

/** Keep the saved queue position, drop removed jobs and append any new ones in sort order (web `mergeQueueOrder`). */
fun mergeQueueOrder(existing: List<String>?, rows: List<QueueRow>, today: LocalDate = LocalDate.now()): List<String> {
    val sortedIds = sortQueueRows(rows, today).map { it.id }
    if (existing.isNullOrEmpty()) return sortedIds
    val known = sortedIds.toSet()
    val seen = HashSet<String>()
    val merged = ArrayList<String>(sortedIds.size)
    for (id in existing) if (id in known && seen.add(id)) merged += id
    for (id in sortedIds) if (seen.add(id)) merged += id
    return merged
}

/** Apply [filters]; "due today" keeps overdue and due-today jobs (web `filterDueToday`). */
fun filterQueueRows(rows: List<QueueRow>, filters: QueueFilters, today: LocalDate = LocalDate.now()): List<QueueRow> = rows.filter { r ->
    (filters.statuses.isEmpty() || r.status in filters.statuses) &&
        (filters.priorities.isEmpty() || r.priority in filters.priorities) &&
        (!filters.dueTodayOnly || collectionUrgency(r.collectionDate, today) <= 1)
}

/** Add [value] when absent, remove it when present. */
fun <T> Set<T>.toggled(value: T): Set<T> = if (value in this) this - value else this + value

/** Move [id] to the front of [order] (undo of a finished or skipped card). */
fun moveToFront(order: List<String>, id: String): List<String> = listOf(id) + order.filter { it != id }

/** Move [id] to the back of [order] (skip). */
fun moveToBack(order: List<String>, id: String): List<String> = order.filter { it != id } + id
