package au.mainspring.nativeapp

import au.mainspring.nativeapp.offline.signOutWarning
import au.mainspring.nativeapp.ui.StatusTone
import au.mainspring.nativeapp.ui.mobileStatusLabel
import au.mainspring.nativeapp.ui.statusTone
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class ColdWalkHubFixesTest {
    private fun hub(service: String, status: String) = HubJob("1", service, "N1", "t", null, status, false, null, false, "k")

    @Test fun mobileActiveFollowsBackendFinalStatuses() {
        listOf("work_completed", "completed", "awaiting_collection", "booking_completed", "collected", "invoice_paid", "no_go", "failed_job").forEach { assertFalse(it, hub("auto_key", it).active) }
        listOf("awaiting_quote", "quote_sent", "go_ahead", "parts_to_order", "on_site", "working_on", "booking_on_hold").forEach { assertTrue(it, hub("auto_key", it).active) }
    }

    @Test fun fetchAllPagesStopsOnShortPageAndCapsPages() = runBlocking {
        val offsets = mutableListOf<Int>()
        val rows = fetchAllPages(2, 5) { o -> offsets += o; if(o < 4) listOf(o, o + 1) else listOf(o) }
        assertEquals(listOf(0, 1, 2, 3, 4), rows); assertEquals(listOf(0, 2, 4), offsets)
        val capped = fetchAllPages(2, 3) { o -> listOf(o, o + 1) }
        assertEquals(6, capped.size)
    }

    @Test fun fetchAllPagesPropagatesFailure() {
        try { runBlocking { fetchAllPages(2, 3) { o -> if(o == 0) listOf(1, 2) else throw java.io.IOException("down") } }; fail() } catch(_: java.io.IOException) {}
    }

    @Test fun partialErrorNamesFailedLanes() {
        assertNull(hubPartialError(emptyList()))
        assertTrue(hubPartialError(listOf("watch"))!!.contains("watch"))
        assertTrue(hubPartialError(listOf("watch", "mobile"))!!.contains("watch or mobile"))
    }

    @Test fun statusFilterSwitchesConflictingDirectory() {
        assertEquals("completed", directoryForStatus("active", "work_completed"))
        assertEquals("completed", directoryForStatus("active", "invoice_paid"))
        assertEquals("active", directoryForStatus("completed", "on_site"))
        assertEquals("active", directoryForStatus("active", "quote_sent"))
        assertEquals("all", directoryForStatus("all", "no_go"))
        assertEquals("active", directoryForStatus("active", null))
    }

    @Test fun mobileLabelsAreCanonical() {
        assertEquals("On Site", mobileStatusLabel("working_on"))
        assertEquals("Quote Sent", mobileStatusLabel("awaiting_go_ahead"))
        assertEquals("Awaiting Booking Confirmation", mobileStatusLabel("go_ahead"))
        assertEquals("Work Completed", mobileStatusLabel("completed"))
        assertEquals("Something new", mobileStatusLabel("something_new"))
    }

    @Test fun missingStatusTonesAreNotNeutral() {
        listOf("booking_on_hold", "sent_to_labanda", "quoted_by_labanda", "at_third_party_repairer", "third_party_quote_approved", "moved_to_pool", "unpaid").forEach { assertEquals(it, StatusTone.Waiting, statusTone(it)) }
        listOf("on_site", "booking_confirmed").forEach { assertEquals(it, StatusTone.Progress, statusTone(it)) }
    }

    @Test fun missingCountsShowDashNotZero() {
        val counts = mapOf("late" to 0, "unscheduled" to 3)
        assertEquals("0", needsActionCountLabel(counts, "late"))
        assertEquals("—", needsActionCountLabel(counts, "on_hold"))
        assertEquals("—", attentionTotalLabel(counts))
        assertEquals("6", attentionTotalLabel(mapOf("late" to 1, "unassigned" to 2, "unscheduled" to 3, "on_hold" to 0)))
    }

    @Test fun leadPipelineIncludesVisitedAndOnboarded() {
        assertTrue(LEAD_STATUS_OPTIONS.map { it.first }.containsAll(listOf("visited", "onboarded")))
    }

    @Test fun signOutWarningMentionsUnsyncedChanges() {
        assertFalse(signOutWarning(0, 0).contains("not yet synced"))
        assertTrue(signOutWarning(2, 0).contains("2 offline changes not yet synced"))
        assertTrue(signOutWarning(1, 1).contains("1 change needing review"))
    }
}
