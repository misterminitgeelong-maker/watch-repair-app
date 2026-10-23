package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.DashboardWidgetsResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DashboardLogicTest {
    private fun w(jobs: Int = 0, quotes: Int = 0, invoices: Int = 0, collection: Int = 0) = DashboardWidgetsResponse(jobs, quotes, invoices, collection)

    @Test fun sweepFollowsTheWebPriorityOrder() {
        assertEquals("watch_jobs", followUpSweepTarget(w(jobs = 1, quotes = 2, invoices = 3, collection = 4)))
        assertEquals("quotes", followUpSweepTarget(w(quotes = 2, invoices = 3, collection = 4)))
        assertEquals("invoices", followUpSweepTarget(w(invoices = 3, collection = 4)))
        assertEquals("watch_jobs", followUpSweepTarget(w(collection = 4)))
    }

    @Test fun sweepIsNullWhenNothingNeedsChasing() {
        assertNull(followUpSweepTarget(w()))
        assertNull(followUpSweepTarget(null))
    }

    @Test fun quotesPendingCountsDraftAndSent() {
        assertEquals(5, quotesPendingCount(mapOf("draft" to 2, "sent" to 3, "approved" to 9)))
        assertEquals(0, quotesPendingCount(emptyMap()))
    }

    @Test fun statusRowsAreLabelledAndSortedByCount() {
        val rows = statusRows(mapOf("awaiting_go_ahead" to 2, "in_progress" to 7, "booked_in" to 2))
        assertEquals(listOf("In progress", "Awaiting go ahead", "Booked in"), rows.map { it.label })
        assertEquals(7, rows.first().count)
    }
}
