package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

class ShoeIntakeWorkflowTest {
    class Fake : ShoeIntakeGateway {
        var customers = 0; var shoes = 0; var jobs = 0; var links = 0; var appends = 0
        var failAppend = false
        val items = mutableListOf<ShoeItemCreate>()
        override suspend fun customer(body: CustomerCreate) = "customer-${++customers}"
        override suspend fun shoe(body: ShoeCreate) = "shoe-${++shoes}"
        override suspend fun job(body: ShoeJobCreate): String { jobs++; items.addAll(body.items); return "shoe-job" }
        override suspend fun link(jobId: String, shoeId: String) { links++ }
        override suspend fun append(jobId: String, items: List<ShoeItemCreate>) { if(failAppend) throw IOException("Response lost"); appends++; this.items.addAll(items) }
    }
    private val catalogue = listOf(ShoeCatalogueItem("heel", "Heel repair", "heels", 2500, "pair"))
    private fun fields() = mutableMapOf("name" to "Avery", "count" to "2", "pair.0.services" to "heel", "pair.1.services" to "heel", "pair.1.price.heel" to "27.35")
    @Test fun multiplePairsShareOneTicketWithPairNotesAndExactPrices() = runBlocking {
        val f = fields(); val g = Fake(); createShoeIntake(f, catalogue, g) { _, _ -> }
        assertEquals(1, g.customers); assertEquals(2, g.shoes); assertEquals(1, g.jobs); assertEquals(1, g.links)
        assertEquals("Pair 1", g.items[0].notes); assertEquals("Pair 2", g.items[1].notes); assertEquals(2735, g.items[1].price)
        createShoeIntake(f, catalogue, g) { _, _ -> }
        assertEquals(1, g.jobs); assertEquals(1, g.links); assertEquals(1, g.appends)
    }
    @Test fun uncertainItemAppendDoesNotRelinkOrCreateAnotherTicket() = runBlocking {
        val f = fields(); val g = Fake().apply { failAppend = true }
        try { createShoeIntake(f, catalogue, g) { _, _ -> }; fail("Expected failure") } catch(_: IOException) {}
        assertEquals("pair.1.itemsSaved", f["uncertain"])
        try { createShoeIntake(f, catalogue, g) { _, _ -> }; fail("Expected guard") } catch(_: IllegalArgumentException) {}
        assertEquals(1, g.jobs); assertEquals(1, g.links)
    }
    @Test fun invalidQuantityIsRejectedBeforeCreatingCustomer() = runBlocking {
        val f = fields().apply { put("pair.1.quantity.heel", "NaN") }; val g = Fake()
        try { createShoeIntake(f, catalogue, g) { _, _ -> }; fail("Expected validation") } catch(_: IllegalArgumentException) {}
        assertEquals(0, g.customers); assertEquals(0, g.shoes)
    }
}
