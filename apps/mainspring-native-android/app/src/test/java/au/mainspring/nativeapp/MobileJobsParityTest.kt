package au.mainspring.nativeapp

import au.mainspring.nativeapp.offline.OfflineKinds
import au.mainspring.nativeapp.offline.OfflineWriteQueue
import au.mainspring.nativeapp.offline.QueuePersistence
import org.junit.Assert.*
import org.junit.Test

class MobileJobsParityTest {
    @Test fun xeroLabelsMatchWeb() {
        assertEquals("Xero: synced", xeroStatusLabel("synced", null))
        assertEquals("Xero: not configured", xeroStatusLabel("skipped", null))
        assertEquals("Xero: failed — boom", xeroStatusLabel("failed", "boom"))
        assertEquals("Xero: —", xeroStatusLabel(null, null))
        assertTrue(canRetryXero("failed")); assertFalse(canRetryXero("synced"))
    }
    @Test fun nextStatusFollowsWeb() {
        assertEquals("en_route", nextMobileStatus("booked"))
        assertEquals("on_site", nextMobileStatus("en_route"))
        assertEquals("work_completed", nextMobileStatus("working_on"))
        assertNull(nextMobileStatus("work_completed"))
        assertEquals("Start trip", quickStatusCopy("en_route"))
        assertTrue(needsCompletionConfirm("work_completed"))
    }
    @Test fun contactHelpers() {
        assertEquals("+61412345678", dialDigits("+61 412 345 678"))
        assertEquals("", dialDigits(null))
        assertNull(directionsUri("  "))
        assertEquals("https://www.google.com/maps/dir/?api=1&destination=1%20High%20St%2C%20Perth", directionsUri("1 High St, Perth"))
    }
    @Test fun bulkSelectionRules() {
        assertEquals(setOf("a"), toggleBulkSelection(emptySet(), "a"))
        assertEquals(emptySet<String>(), toggleBulkSelection(setOf("a"), "a"))
        assertEquals(setOf("a"), toggleBulkSelection(setOf("a"), "b", max = 1))
        assertEquals(setOf("a", "b"), toggleSelectAll(emptySet(), listOf("a", "b")))
        assertEquals(emptySet<String>(), toggleSelectAll(setOf("a", "b"), listOf("a", "b")))
        assertEquals(setOf("a"), pruneBulkSelection(setOf("a", "z"), listOf("a", "b")))
        assertNotNull(bulkProblem(emptySet(), "en_route")); assertNotNull(bulkProblem(setOf("a"), "bogus"))
        assertNull(bulkProblem(setOf("a"), "en_route"))
    }
    @Test fun savedViewIsSanitised() {
        assertEquals(MobileSavedView("active", null), sanitizeSavedView(MobileSavedView("zzz", "bad")))
        assertEquals(MobileSavedView("all", "today"), sanitizeSavedView(MobileSavedView("all", "today")))
        assertEquals(MobileSavedView("completed", "today"), mobileViewToSaved(mobileViewOf("completed", "today", "")))
    }
    @Test fun mobileNoteIsQueuedAndSupersededKeepingOriginalVersion() {
        var saved: String? = null
        val q = OfflineWriteQueue(object : QueuePersistence { override fun load() = saved; override fun save(json: String?) { saved = json } }, { "scope" })
        assertTrue(q.enqueue(OfflineKinds.MOBILE_NOTE, "v1/auto-key-jobs/j1", "PATCH", "{\"tech_notes\":\"one\"}", "j1", "n1", "v1"))
        assertTrue(q.enqueue(OfflineKinds.MOBILE_NOTE, "v1/auto-key-jobs/j1", "PATCH", "{\"tech_notes\":\"two\"}", "j1", "n2", "v2"))
        val pending = q.state.value.pending
        assertEquals(1, pending.size)
        assertTrue(pending[0].body.contains("two"))
        assertEquals("v1", pending[0].expectedUpdatedAt)
    }
}
