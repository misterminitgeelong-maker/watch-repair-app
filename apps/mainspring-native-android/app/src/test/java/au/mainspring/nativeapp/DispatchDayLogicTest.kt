package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.AutoKeyJobRead
import org.junit.Assert.*
import org.junit.Test
import java.time.LocalDate

class DispatchDayLogicTest {
    private val today = LocalDate.of(2026, 10, 20)
    private fun job(id: String, status: String = "awaiting_quote", at: String? = null, tech: String? = null, customer: String = "c1") = AutoKeyJobRead(
        id = id, tenantId = "t", customerId = customer, jobNumber = "AK-$id", statusToken = "s", title = "x", keyQuantity = 1, programmingStatus = "p",
        priority = "normal", status = status, depositCents = 0, costCents = 0, createdAt = "2026-10-15T09:00:00Z", scheduledAt = at,
        commissionLeadSource = "other", assignedUserId = tech)

    @Test fun pickingTodayMeansLiveList() = assertNull(resolveDispatchDay(today, today))
    @Test fun pickingAnotherDayIsKept() = assertEquals(today.plusDays(3), resolveDispatchDay(today.plusDays(3), today))
    @Test fun labelsNearDaysAndFormatsOthers() {
        assertEquals("Today", dispatchDayLabel(null, today))
        assertEquals("Tomorrow", dispatchDayLabel(today.plusDays(1), today))
        assertEquals("Yesterday", dispatchDayLabel(today.minusDays(1), today))
        assertEquals("Fri 23 Oct", dispatchDayLabel(LocalDate.of(2026, 10, 23), today))
    }
    @Test fun unscheduledKeepsOnlyOpenJobsWithoutATime() {
        val rows = listOf(job("1"), job("2", at = "2026-10-21T01:00:00Z"), job("3", status = "work_completed"), job("4", status = "cancelled"))
        assertEquals(listOf("1"), dispatchUnscheduled(rows, "all").map { it.id })
    }
    @Test fun unscheduledRespectsTechnicianLane() {
        val rows = listOf(job("1", tech = "u1"), job("2", tech = "u2"), job("3"))
        assertEquals(listOf("1"), dispatchUnscheduled(rows, "u1").map { it.id })
        assertEquals(listOf("3"), dispatchUnscheduled(rows, "none").map { it.id })
        assertEquals(3, dispatchUnscheduled(rows, "all").size)
    }
    @Test fun posLinkableJobsAreOpenJobsOfThatCustomer() {
        val rows = listOf(job("1"), job("2", customer = "c2"), job("3", status = "collected"), job("4", status = "on_site"))
        assertEquals(listOf("1", "4"), posLinkableJobs(rows, "c1").map { it.id })
        assertTrue(posLinkableJobs(rows, "").isEmpty())
    }
}
