package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.ShoeRepairJobRead

/** Shoe queue lane in order; mirrors web `RepairQueueModal` STATUS_NEXT keys plus its terminal step. */
val SHOE_QUEUE_SEQUENCE: List<String> = listOf(
    "awaiting_quote", "awaiting_go_ahead", "go_ahead", "working_on", "completed", "awaiting_collection", "collected",
)

/** The next status the shoe queue advances a job to, or null at the end of the lane (web `STATUS_NEXT`). */
fun nextShoeQueueStatus(status: String): String? {
    val i = SHOE_QUEUE_SEQUENCE.indexOf(status)
    return if (i < 0) null else SHOE_QUEUE_SEQUENCE.getOrNull(i + 1)
}

/** Shoe jobs the queue can triage: on the lane and not yet collected, ordered by due date (no date last), then job number. */
fun shoeQueueEligibleJobs(jobs: List<ShoeRepairJobRead>): List<ShoeRepairJobRead> = jobs
    .filter { it.status in SHOE_QUEUE_SEQUENCE && it.status != "collected" }
    .sortedWith(compareBy<ShoeRepairJobRead> { it.collectionDate.isNullOrBlank() }.thenBy { it.collectionDate.orEmpty() }.thenBy { it.jobNumber })
