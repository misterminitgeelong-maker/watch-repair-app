package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.RepairJobRead
import java.time.LocalDate

/** Linear watch queue lane; mirrors backend `_WATCH_QUEUE_SEQUENCE`. */
val WATCH_QUEUE_SEQUENCE: List<String> = listOf(
    "awaiting_quote", "awaiting_go_ahead", "go_ahead", "at_third_party_for_quoting",
    "third_party_quote_approved", "at_third_party_repairer", "awaiting_parts", "working_on",
    "completed", "awaiting_collection", "collected",
)

/** The status a swipe would produce ("right" = forward, "left" = back), or null when not possible. */
fun previewQueueSwipe(status: String, direction: String): String? {
    val i = WATCH_QUEUE_SEQUENCE.indexOf(status)
    if (i < 0) return null
    return when (direction) {
        "right" -> WATCH_QUEUE_SEQUENCE.getOrNull(i + 1)
        "left" -> WATCH_QUEUE_SEQUENCE.getOrNull(i - 1)
        else -> null
    }
}

fun RepairJobRead.toQueueRow() = QueueRow(id, status, priority, collectionDate, createdAt)

/** Jobs the queue can triage: on the lane and not yet collected, in queue order (urgency, priority, age; web `sortQueue`). */
fun queueEligibleJobs(jobs: List<RepairJobRead>, today: LocalDate = LocalDate.now()): List<RepairJobRead> {
    val eligible = jobs.filter { it.status in WATCH_QUEUE_SEQUENCE && it.status != "collected" }
    val byId = eligible.associateBy { it.id }
    return sortQueueRows(eligible.map { it.toQueueRow() }, today).mapNotNull { byId[it.id] }
}
