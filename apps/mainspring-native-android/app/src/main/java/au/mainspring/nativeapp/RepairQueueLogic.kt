package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.RepairJobRead

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

/** Jobs the queue can triage: on the lane and not yet collected, ordered by due date (no date last), then job number. */
fun queueEligibleJobs(jobs: List<RepairJobRead>): List<RepairJobRead> = jobs
    .filter { it.status in WATCH_QUEUE_SEQUENCE && it.status != "collected" }
    .sortedWith(compareBy<RepairJobRead> { it.collectionDate.isNullOrBlank() }.thenBy { it.collectionDate.orEmpty() }.thenBy { it.jobNumber })
