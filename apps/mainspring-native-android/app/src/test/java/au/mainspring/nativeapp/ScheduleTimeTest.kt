package au.mainspring.nativeapp

import org.junit.Assert.*
import org.junit.Test

class ScheduleTimeTest {
    @Test fun bookingUsesShopTimezoneAndPreservesOptionalDates() {
        assertNull(scheduledTimeIso("", "Australia/Sydney"))
        assertEquals("2026-10-09T09:30+11:00", scheduledTimeIso("09/10/2026 09:30", "Australia/Sydney"))
    }
    @Test(expected = IllegalArgumentException::class) fun nonexistentSpringTimeIsRejected() {
        scheduledTimeIso("04/10/2026 02:30", "Australia/Sydney")
    }
    @Test(expected = IllegalArgumentException::class) fun ambiguousAutumnTimeIsRejected() {
        scheduledTimeIso("05/04/2026 02:30", "Australia/Sydney")
    }
}
