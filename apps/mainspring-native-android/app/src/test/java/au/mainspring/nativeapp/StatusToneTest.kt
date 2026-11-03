package au.mainspring.nativeapp

import au.mainspring.nativeapp.ui.StatusTone
import au.mainspring.nativeapp.ui.statusTone
import org.junit.Assert.assertEquals
import org.junit.Test

class StatusToneTest {
    @Test fun waitingStates() {
        listOf("awaiting_parts", "awaiting_quote", "awaiting_go_ahead", "quote_sent", "Awaiting approval", "pending").forEach { assertEquals(it, StatusTone.Waiting, statusTone(it)) }
    }
    @Test fun readyStates() {
        listOf("awaiting_collection", "work_completed", "completed", "collected", "paid", "invoice_paid", "ready").forEach { assertEquals(it, StatusTone.Ready, statusTone(it)) }
    }
    @Test fun progressStates() {
        listOf("in_progress", "working_on", "go_ahead", "en_route", "In progress").forEach { assertEquals(it, StatusTone.Progress, statusTone(it)) }
    }
    @Test fun lateStates() {
        listOf("overdue", "urgent", "no_go", "job_delayed", "failed_job", "declined").forEach { assertEquals(it, StatusTone.Late, statusTone(it)) }
    }
    @Test fun unknownAndBlankAreNeutral() {
        assertEquals(StatusTone.Neutral, statusTone(""))
        assertEquals(StatusTone.Neutral, statusTone("draft"))
        assertEquals(StatusTone.Neutral, statusTone("something_new"))
    }
}
