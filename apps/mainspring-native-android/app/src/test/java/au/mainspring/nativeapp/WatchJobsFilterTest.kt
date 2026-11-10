package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.RepairJobRead
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WatchJobsFilterTest {
    private fun job(id: String, status: String) = RepairJobRead(id = id, tenantId = "t", watchId = "w", jobNumber = "J-$id", title = "Service", description = null,
        status = status, priority = "normal", customerName = null, createdAt = "2026-10-08T00:00:00Z")

    @Test fun collectedAndClosedStatusesAreCompleted() {
        assertTrue(isWatchCompleted("collected"))
        listOf("awaiting_quote", "working_on", "awaiting_collection", "completed", "no_go", "invoice_paid", "failed_job").forEach { assertFalse(it, isWatchCompleted(it)) }
    }

    @Test fun activeAndCompletedTabsSplitTheLoadedJobsAndCountThem() {
        val jobs = listOf(job("1", "awaiting_quote"), job("2", "collected"), job("3", "awaiting_collection"), job("4", "no_go"))
        val active = JobsUiState(jobs = jobs)
        assertEquals(listOf("1", "3", "4"), active.visibleJobs.map { it.id }.sorted())
        assertEquals(3, active.activeCount); assertEquals(1, active.completedCount)
        assertEquals(listOf("2"), active.copy(showCompleted = true).visibleJobs.map { it.id }.sorted())
    }

    @Test fun filterBadgeCountsOnlyNonDefaultChoices() {
        assertEquals(0, JobsUiState().activeFilterCount)
        assertEquals(3, JobsUiState(statusFilter = "working_on", sort = JobSort.OLDEST, minDaysInShop = 7).activeFilterCount)
    }
}
