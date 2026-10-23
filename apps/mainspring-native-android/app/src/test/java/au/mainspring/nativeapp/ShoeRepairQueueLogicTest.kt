package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.ShoeRepairJobRead
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ShoeRepairQueueLogicTest {
    private fun job(id: String, status: String, due: String? = null) = ShoeRepairJobRead(
        id = id, tenantId = "t", shoeId = "s", jobNumber = id, statusToken = "tok", title = id, priority = "normal", status = status,
        collectionDate = due, depositCents = 0, costCents = 0, quoteApprovalToken = "q", quoteStatus = "none", createdAt = "2026-10-08T00:00:00Z",
    )

    @Test fun nextStatusMapMatchesWeb() {
        assertEquals("awaiting_go_ahead", nextShoeQueueStatus("awaiting_quote"))
        assertEquals("go_ahead", nextShoeQueueStatus("awaiting_go_ahead"))
        assertEquals("working_on", nextShoeQueueStatus("go_ahead"))
        assertEquals("completed", nextShoeQueueStatus("working_on"))
        assertEquals("awaiting_collection", nextShoeQueueStatus("completed"))
        assertEquals("collected", nextShoeQueueStatus("awaiting_collection"))
        assertNull(nextShoeQueueStatus("collected"))
        assertNull(nextShoeQueueStatus("no_go"))
        assertNull(nextShoeQueueStatus("awaiting_parts"))
    }

    @Test fun queueKeepsLaneJobsOrderedByUrgencyThenAge() {
        val ids = shoeQueueEligibleJobs(listOf(
            job("S-3", "working_on"), job("S-2", "go_ahead", "2026-10-12"), job("S-1", "awaiting_quote", "2026-10-10"),
            job("S-0", "completed"), job("S-4", "collected"), job("S-5", "no_go"), job("S-6", "quote_sent"),
        ), java.time.LocalDate.of(2026, 10, 20)).map { it.id }
        assertEquals(listOf("S-1", "S-2", "S-3", "S-0"), ids)
    }
}
