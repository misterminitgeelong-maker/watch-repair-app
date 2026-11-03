package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.AutoKeyJobRead
import org.junit.Assert.*
import org.junit.Test

class RouteFiltersTest {
    private fun job(id: String, tech: String?, status: String) = AutoKeyJobRead(
        id = id, tenantId = "t", customerId = "c", jobNumber = "AK-$id", statusToken = "s", title = id, keyQuantity = 1, programmingStatus = "p",
        priority = "normal", status = status, depositCents = 0, costCents = 0, createdAt = "2026-10-15T09:00:00Z", commissionLeadSource = "other", assignedUserId = tech)
    private val jobs = listOf(job("a", "u1", "booked"), job("b", "u2", "booked"), job("c", null, "en_route"), job("d", "u1", "en_route"))

    @Test fun noFiltersKeepsEverything() = assertEquals(4, filterRouteJobs(jobs, null, null).size)
    @Test fun technicianFilter() = assertEquals(listOf("a", "d"), filterRouteJobs(jobs, "u1", null).map { it.id })
    @Test fun unassignedFilter() = assertEquals(listOf("c"), filterRouteJobs(jobs, ROUTE_UNASSIGNED, null).map { it.id })
    @Test fun statusFilter() = assertEquals(listOf("c", "d"), filterRouteJobs(jobs, null, "en_route").map { it.id })
    @Test fun filtersCombine() = assertEquals(listOf("d"), filterRouteJobs(jobs, "u1", "en_route").map { it.id })

    @Test fun moveItemDownAndUp() {
        assertEquals(listOf("b", "a", "c"), moveItem(listOf("a", "b", "c"), 0, 1))
        assertEquals(listOf("c", "a", "b"), moveItem(listOf("a", "b", "c"), 2, 0))
    }
    @Test fun moveItemOutOfRangeIsNoOp() {
        val list = listOf("a", "b")
        assertSame(list, moveItem(list, 0, -1))
        assertSame(list, moveItem(list, 1, 2))
        assertSame(list, moveItem(list, 1, 1))
    }
}
