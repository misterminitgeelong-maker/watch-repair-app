package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.DispatchPoolJob
import au.mainspring.nativeapp.api.TenantEventLogRead
import com.google.gson.Gson
import org.junit.Assert.*
import org.junit.Test

class NativeReleaseParityTest {
    @Test fun redactedPoolPayloadDoesNotRequirePersonalDetails() {
        val job = Gson().fromJson("""{"id":"pool-1","job_type":"Mobile Key","suburb":"Geelong","state":"VIC","postcode":"3220","vehicle_make":"Ford","ring":1,"created_at":"2026-11-11T00:00:00Z"}""", DispatchPoolJob::class.java)
        assertNull(job.customerName); assertNull(job.address); assertNull(job.plate)
        assertEquals("Geelong", job.suburb); assertEquals("Mobile Key", job.jobType)
    }
    @Test fun networkPushRoutesPreserveOnlyValidatedNavigation() {
        assertEquals("networkMessages", PushRoutes.toRoute("/messages"))
        assertEquals("networkMessages?conversation=abc-123", PushRoutes.toRoute("/messages?c=abc-123"))
        assertEquals("networkMessages?tab=announcements", PushRoutes.toRoute("/messages?tab=announcements"))
        assertEquals("messages/auto-key-jobs/abc", PushRoutes.toRoute("/auto-key/abc?tab=messages"))
        assertEquals("networkMessages?network=n1&hub=VIC", PushRoutes.toRoute("/messages?network=n1&hub=VIC"))
        assertEquals("networkMessages", PushRoutes.toRoute("/messages?c=../../jobs&redirect=evil"))
        assertNull(PushRoutes.toRoute("https://evil.example/messages?c=abc"))
    }
    @Test fun announcementAndHqAlertsCanBeOpenedWithoutEntityId() {
        val a = TenantEventLogRead("a", eventType = "network_announcement", eventSummary = "News", createdAt = "2026-11-11")
        assertEquals("networkMessages?tab=announcements", inboxRoute(a))
        assertEquals("hqAlert/a", inboxRoute(a.copy(eventType = "hq_message")))
    }
    @Test fun minimumVersionBoundaryKeepsCurrentClientsUsable() {
        assertFalse(requiresNativeUpdate(0, 1)); assertFalse(requiresNativeUpdate(42, 42))
        assertTrue(requiresNativeUpdate(43, 42)); assertFalse(requiresNativeUpdate(41, 42))
    }
}
