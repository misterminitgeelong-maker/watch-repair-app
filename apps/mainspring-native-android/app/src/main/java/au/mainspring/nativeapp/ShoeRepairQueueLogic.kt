package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.ShoeRepairJobRead
import java.time.LocalDate

/** Shoe queue lane in order; mirrors web `RepairQueueModal` STATUS_NEXT keys plus its terminal step. */
val SHOE_QUEUE_SEQUENCE: List<String> = listOf(
    "awaiting_quote", "awaiting_go_ahead", "go_ahead", "working_on", "completed", "awaiting_collection", "collected",
)

/** The next status the shoe queue advances a job to, or null at the end of the lane (web `STATUS_NEXT`). */
fun nextShoeQueueStatus(status: String): String? {
    val i = SHOE_QUEUE_SEQUENCE.indexOf(status)
    return if (i < 0) null else SHOE_QUEUE_SEQUENCE.getOrNull(i + 1)
}

/** The status a back step returns to (used by undo only; the shoe lane has no back swipe). */
fun previousShoeQueueStatus(status: String): String? {
    val i = SHOE_QUEUE_SEQUENCE.indexOf(status)
    return if (i <= 0) null else SHOE_QUEUE_SEQUENCE[i - 1]
}

fun ShoeRepairJobRead.toQueueRow() = QueueRow(id, status, priority, collectionDate, createdAt)

/** Shoe jobs the queue can triage: on the lane and not yet collected, in queue order (urgency, priority, age). */
fun shoeQueueEligibleJobs(jobs: List<ShoeRepairJobRead>, today: LocalDate = LocalDate.now()): List<ShoeRepairJobRead> {
    val eligible = jobs.filter { it.status in SHOE_QUEUE_SEQUENCE && it.status != "collected" }
    val byId = eligible.associateBy { it.id }
    return sortQueueRows(eligible.map { it.toQueueRow() }, today).mapNotNull { byId[it.id] }
}
