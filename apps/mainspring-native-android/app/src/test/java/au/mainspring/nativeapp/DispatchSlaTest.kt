package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.AutoKeyJobRead
import org.junit.Assert.*
import org.junit.Test
import java.time.Instant

class DispatchSlaTest {
    private val now = Instant.parse("2026-10-15T10:00:00Z")
    private fun job(status: String = "booking_confirmed", at: String? = null, created: String = "2026-10-15T09:00:00Z", visit: Int? = null) = AutoKeyJobRead(
        id = "j", tenantId = "t", customerId = "c", jobNumber = "AK-1", statusToken = "s", title = "x", keyQuantity = 1, programmingStatus = "p",
        priority = "normal", status = status, depositCents = 0, costCents = 0, createdAt = created, scheduledAt = at, commissionLeadSource = "other", visitOrder = visit)

    @Test fun pastBookingIsLate() = assertEquals(SlaKind.LATE, slaChip(job(at = "2026-10-15T09:30:00Z"), now))
    @Test fun within30MinutesIsAtRisk() = assertEquals(SlaKind.AT_RISK, slaChip(job(at = "2026-10-15T10:20:00Z"), now))
    @Test fun laterBookingHasNoChip() = assertNull(slaChip(job(at = "2026-10-15T12:00:00Z"), now))
    @Test fun enRouteStopsTheClock() = assertNull(slaChip(job(status = "en_route", at = "2026-10-15T09:00:00Z"), now))
    @Test fun closedHasNoChip() = assertNull(slaChip(job(status = "work_completed", at = "2026-10-15T09:00:00Z"), now))
    @Test fun oldUnscheduledIsAging() = assertEquals(SlaKind.AGING, slaChip(job(created = "2026-10-14T09:00:00Z"), now))
    @Test fun newUnscheduledHasNoChip() = assertNull(slaChip(job(), now))
    @Test fun visitOrderBeatsTime() {
        val a = job(at = "2026-10-15T08:00:00Z", visit = 2); val b = job(at = "2026-10-15T09:00:00Z", visit = 1)
        assertTrue(compareByVisitThenTime(b, a) < 0)
        assertTrue(compareByVisitThenTime(job(visit = 1), job(at = "2026-10-15T08:00:00Z")) < 0)
    }
}
