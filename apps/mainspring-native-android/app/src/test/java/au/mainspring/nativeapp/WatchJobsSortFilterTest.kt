package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.RepairJobRead
import java.time.LocalDate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WatchJobsSortFilterTest {
    private fun job(id: String, number: String, status: String = "working_on", priority: String = "normal", due: String? = null) = RepairJobRead(
        id = id, tenantId = "t", watchId = "w", jobNumber = number, title = "Service", description = null,
        status = status, priority = priority, customerName = null, createdAt = "2026-10-08T00:00:00Z", collectionDate = due,
    )

    @Test fun jobNumberSortIsNumericAwareBothWays() {
        val jobs = listOf(job("a", "10"), job("b", "9"), job("c", "100"))
        assertEquals(listOf("c", "a", "b"), sortJobs(jobs, JobSort.JOB_NUMBER, descending = true).map { it.id })
        assertEquals(listOf("b", "a", "c"), sortJobs(jobs, JobSort.JOB_NUMBER, descending = false).map { it.id })
    }

    @Test fun prioritySortPutsUrgentFirstWhenDescending() {
        val jobs = listOf(job("a", "1", priority = "low"), job("b", "2", priority = "urgent"), job("c", "3", priority = "normal"))
        assertEquals(listOf("b", "c", "a"), sortJobs(jobs, JobSort.PRIORITY, descending = true).map { it.id })
        assertEquals(listOf("a", "c", "b"), sortJobs(jobs, JobSort.PRIORITY, descending = false).map { it.id })
    }

    @Test fun statusSortGroupsByStatus() {
        val jobs = listOf(job("a", "1", status = "working_on"), job("b", "2", status = "awaiting_quote"))
        assertEquals(listOf("b", "a"), sortJobs(jobs, JobSort.STATUS, descending = false).map { it.id })
    }

    @Test fun serverSortParameters() {
        assertEquals("job_number", JobSort.JOB_NUMBER.apiField)
        assertEquals("created_at", JobSort.NEWEST.apiField)
        assertEquals("asc", sortDirParam(JobSort.OLDEST, true))
        assertEquals("desc", sortDirParam(JobSort.NEWEST, false))
        assertEquals("asc", sortDirParam(JobSort.STATUS, false))
        assertEquals("desc", sortDirParam(JobSort.PRIORITY, true))
    }

    @Test fun pastCollectionOnlyKeepsJobsDueBeforeToday() {
        val today = LocalDate.of(2026, 10, 20)
        assertTrue(isPastCollection("2026-10-19", today))
        assertFalse(isPastCollection("2026-10-20", today))
        assertFalse(isPastCollection(null, today))
        val state = JobsUiState(jobs = listOf(job("a", "1", due = "2026-01-01"), job("b", "2", due = "2999-01-01"), job("c", "3")), pastCollectionOnly = true)
        assertEquals(listOf("a"), state.visibleJobs.map { it.id })
    }

    @Test fun filterBadgeCountsNewFilters() {
        assertEquals(2, JobsUiState(costOutliersOnly = true, pastCollectionOnly = true).activeFilterCount)
    }

    @Test fun movementQuoteSetsCostAndPreQuote() {
        val f = movementQuoteFields(12500)
        assertEquals(12500, f["cost_cents"].asInt)
        assertEquals(12500, f["pre_quote_cents"].asInt)
    }

    @Test fun workflowStepTapTargetsTheFirstStatusOfTheStep() {
        val collected = WATCH_WORKFLOW_STEPS.first { it.key == "collected" }
        assertEquals("awaiting_collection", collected.statuses.first())
    }
}
