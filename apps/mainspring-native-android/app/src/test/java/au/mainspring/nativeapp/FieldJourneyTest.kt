package au.mainspring.nativeapp

import org.junit.Assert.*
import org.junit.Test

class FieldJourneyTest {
    @Test fun onlyConfirmedBookingsSuggestDeparture() {
        assertEquals("en_route",fieldJourney("booked").targetStatus)
        assertEquals("en_route",fieldJourney("booking_confirmed").targetStatus)
        assertNull(fieldJourney("awaiting_booking_confirmation").targetStatus)
        assertNull(fieldJourney("pending_booking").targetStatus)
    }
    @Test fun travelSuggestsArrivalAndCompletionNeverClaimsPayment() {
        assertEquals("on_site",fieldJourney("en_route").targetStatus)
        assertEquals(2,fieldJourney("on_site").step)
        assertEquals(3,fieldJourney("work_completed").step)
        assertEquals(4,fieldJourney("invoice_paid").step)
        assertTrue(fieldJourney("work_completed").action.contains("payment"))
    }
    @Test fun waitingApprovalAndExceptionalStatesNeverSuggestAStatusWrite() {
        listOf("awaiting_go_ahead","quote_sent","awaiting_quote","failed_job","no_go","job_delayed","awaiting_parts").forEach {assertNull(fieldJourney(it).targetStatus)}
    }
}
