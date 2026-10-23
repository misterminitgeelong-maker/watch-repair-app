package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.RepairJobRead
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RepairQueueLogicTest {
    private fun job(id: String, status: String, due: String? = null) = RepairJobRead(
        id = id, tenantId = "t", watchId = "w", jobNumber = id, title = id, description = null,
        status = status, priority = "normal", customerName = null, createdAt = "2026-10-08T00:00:00Z", collectionDate = due,
    )

    @Test fun previewFollowsTheLane() {
        assertEquals("awaiting_go_ahead", previewQueueSwipe("awaiting_quote", "right"))
        assertEquals("awaiting_quote", previewQueueSwipe("awaiting_go_ahead", "left"))
        assertNull(previewQueueSwipe("awaiting_quote", "left"))
        assertNull(previewQueueSwipe("collected", "right"))
        assertNull(previewQueueSwipe("no_go", "right"))
        assertNull(previewQueueSwipe("working_on", "up"))
    }

    @Test fun queueKeepsLaneJobsOrderedByDueDate() {
        val ids = queueEligibleJobs(listOf(
            job("W-3", "working_on"), job("W-2", "go_ahead", "2026-10-12"), job("W-1", "awaiting_quote", "2026-10-10"),
            job("W-4", "collected"), job("W-5", "no_go"), job("W-6", "service"),
        )).map { it.id }
        assertEquals(listOf("W-1", "W-2", "W-3"), ids)
    }
}
