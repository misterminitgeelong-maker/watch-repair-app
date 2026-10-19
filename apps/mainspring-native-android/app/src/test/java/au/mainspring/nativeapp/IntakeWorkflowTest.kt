package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

class IntakeWorkflowTest {
    class FakeGateway : IntakeGateway {
        var customers = 0; var watches = 0
        val jobs = mutableListOf<RepairJobCreate>()
        var failJob = false
        override suspend fun customer(body: CustomerCreate) = "customer-${++customers}"
        override suspend fun watch(body: WatchCreate) = "watch-${++watches}"
        override suspend fun job(body: RepairJobCreate): String {
            if (failJob) throw IOException("Response lost")
            jobs.add(body); return "job-${jobs.size}"
        }
    }
    private fun fields() = mutableMapOf("name" to "Sam", "title" to "Battery", "deposit" to "12.35", "collection" to "09/10/2026")
    @Test fun multiWatchMatchesWebTicketAmountsAndTitles() = runBlocking {
        val f = fields().apply { put("watchCount", "2"); put("ticketOverride", "123") }
        val g = FakeGateway()
        val ids = createIntakeTickets(f, g) { _, _ -> }
        assertEquals(listOf("job-1", "job-2"), ids)
        assertEquals(1, g.customers); assertEquals(2, g.watches)
        assertEquals("Battery (Watch 2 of 2)", g.jobs[1].title)
        assertEquals(1235, g.jobs[0].depositCents); assertEquals(1235, g.jobs[1].depositCents)
        assertEquals("2026-10-09", g.jobs[0].collectionDate)
        assertNull(g.jobs[0].jobNumberOverride)
    }
    @Test fun acknowledgedTicketsAreNotCreatedAgainOnRetry() = runBlocking {
        val f = fields(); val g = FakeGateway()
        val first = createIntakeTickets(f, g) { _, _ -> }
        assertEquals(first, createIntakeTickets(f, g) { _, _ -> })
        assertEquals(1, g.customers); assertEquals(1, g.watches); assertEquals(1, g.jobs.size)
    }
    @Test fun unknownResponseBlocksBlindRetryAndPreservesAcknowledgedResources() = runBlocking {
        val f = fields(); val g = FakeGateway().apply { failJob = true }
        try { createIntakeTickets(f, g) { _, _ -> }; fail("Expected failure") } catch (_: IOException) {}
        assertEquals("job.0.id", f["uncertainWrite"])
        assertEquals("true",f["hasAcknowledgement"])
        g.failJob = false
        try { createIntakeTickets(f, g) { _, _ -> }; fail("Expected reconciliation guard") } catch (_: IllegalArgumentException) {}
        assertEquals(1, g.customers); assertEquals(1, g.watches); assertEquals(0, g.jobs.size)
    }
    @Test fun invalidFinancialInputDoesNotCreateAnyRecords() = runBlocking {
        val f = fields().apply { put("deposit", "-1") }; val g = FakeGateway()
        try { createIntakeTickets(f, g) { _, _ -> }; fail("Expected validation") } catch (_: IllegalArgumentException) {}
        assertEquals(0, g.customers); assertEquals(0, g.watches)
    }
    @Test fun datesRejectImpossibleDatesAndMoneyIsExact() {
        assertEquals(29, dollarsToCentsChecked("0.29"))
        try { collectionDateIso("31/02/2026"); fail("Expected invalid date") } catch (_: java.time.format.DateTimeParseException) {}
        assertEquals("2028-02-29", collectionDateIso("29/02/2028"))
    }
    @Test fun catalogueComboAndBandDiscountMatchWebPricing() {
        val items = listOf(WatchCatalogueItem("battery", "Battery", 2000, "fixed", null), WatchCatalogueItem("band", "Band", 2999, "fixed", null))
        assertEquals(4399, repairsTotal(items, listOf(WatchRepairsCombo(batteryKey = "battery", bandKeys = listOf("band"), bandDiscountPercent = 20.0))))
        assertEquals(3900, repairsTotal(items, listOf(WatchRepairsCombo(keys = listOf("battery", "band"), totalCents = 3900))))
    }
}
