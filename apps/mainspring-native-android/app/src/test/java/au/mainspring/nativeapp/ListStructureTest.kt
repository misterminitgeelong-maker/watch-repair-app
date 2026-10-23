package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.TenantEventLogRead
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.Instant
import java.time.ZoneId

class ListStructureTest {
    private fun job(id: String, customer: String?, due: String?, created: String) =
        HubJob(id, "watch", id, "t", customer, "in_progress", false, due, false, (due ?: "9999") + id, created)
    private fun ev(id: String, type: String, at: String, entity: String? = null) = TenantEventLogRead(id, null, type, "s", at, entity, null)

    @Test fun jobSortsOrderAsExpected() {
        val jobs = listOf(job("a", "Zed", "2026-10-05", "2026-01-02"), job("b", "amy", null, "2026-03-01"), job("c", null, "2026-10-01", "2026-02-01"))
        assertEquals(listOf("c", "a", "b"), sortHubJobs(jobs, "default").map { it.id })
        assertEquals(listOf("b", "c", "a"), sortHubJobs(jobs, "newest").map { it.id })
        assertEquals(listOf("a", "c", "b"), sortHubJobs(jobs, "oldest").map { it.id })
        assertEquals(listOf("c", "a", "b"), sortHubJobs(jobs, "due").map { it.id })
        assertEquals(listOf("b", "a", "c"), sortHubJobs(jobs, "customer").map { it.id })
    }

    @Test fun countLabelPluralises() {
        assertEquals("13 jobs", countLabel(13, "job")); assertEquals("1 customer", countLabel(1, "customer")); assertEquals("100+ customers", countLabel(100, "customer", more = true))
    }

    @Test fun alphaSectionsGroupConsecutiveLetters() {
        val s = alphaSections(listOf("amy", "Adam", "Bob", "7-Eleven", "  ", "Zoe")) { it }
        assertEquals(listOf("A", "B", "#", "Z"), s.map { it.first })
        assertEquals(2, s[0].second.size); assertEquals(2, s[2].second.size)
    }

    @Test fun inboxCategoriesAndFilter() {
        assertEquals("money", inboxCategory(ev("1", "card_payment_needs_attention", "x")))
        assertEquals("messages", inboxCategory(ev("2", "customer_sms_reply", "x")))
        assertEquals("jobs", inboxCategory(ev("3", "repair_job_updated", "x")))
        assertEquals(listOf("2"), filterInbox(listOf(ev("1", "card_payment", "x"), ev("2", "portal_customer_message", "x")), "messages").map { it.id })
    }

    @Test fun dayBucketsRelativeToNow() {
        val zone = ZoneId.of("Australia/Sydney"); val now = Instant.parse("2026-10-17T02:00:00Z")
        assertEquals("Today", dayBucket("2026-10-17T00:30:00Z", now, zone))
        assertEquals("Yesterday", dayBucket("2026-10-16T05:00:00Z", now, zone))
        assertEquals("This week", dayBucket("2026-10-13T05:00:00Z", now, zone))
        assertEquals("Earlier", dayBucket("2026-10-01T00:00:00Z", now, zone))
        assertEquals("Earlier", dayBucket("garbage", now, zone))
        val sections = inboxDaySections(listOf(ev("a", "x", "2026-10-01T00:00:00Z"), ev("b", "x", "2026-10-17T00:30:00Z")), now, zone)
        assertEquals(listOf("Today", "Earlier"), sections.map { it.first })
    }
}
