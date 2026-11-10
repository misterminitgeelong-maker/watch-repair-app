package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.ui.*
import com.google.gson.Gson
import com.google.gson.JsonParser
import org.junit.Assert.*
import org.junit.Test

class WatchParityTest {
    @Test fun watchQuoteTypesReachTheApiAndDiscountTotalsMatchTheServer() {
        val draft = QuoteComposerDraft(lines = listOf(
            QuoteLineDraft("New movement", "1", "200", itemType = "part"),
            QuoteLineDraft("Fit movement", "1", "100", itemType = "labor"),
            QuoteLineDraft("Loyalty discount", "1", "30", itemType = "discount")))
        val lines = quoteLinesFromDraft(draft.lines)
        assertEquals(listOf("part", "labor", "discount"), lines.map { it.itemType })
        assertEquals(27000, quotePreview(draft, "AUD").total.toInt())
        val body = QuoteCreate("job", true, true, lines.map { QuoteLineItemRead(description = it.description, quantity = it.quantity, unitPriceCents = it.unitCents, itemType = it.itemType!!) })
        val json = JsonParser.parseString(Gson().toJson(body)).asJsonObject
        assertEquals("discount", json.getAsJsonArray("line_items")[2].asJsonObject["item_type"].asString)
        assertEquals(3000, json.getAsJsonArray("line_items")[2].asJsonObject["unit_price_cents"].asInt)
    }
    @Test fun discountsCannotProduceNegativeQuotesAndOldDraftsKeepLabourType() {
        assertThrows(IllegalArgumentException::class.java) { quoteLinesFromDraft(listOf(QuoteLineDraft("Discount", "1", "10", itemType = "discount"))) }
        val old = Gson().fromJson("""{"description":"Service","quantity":"1","price":"45"}""", QuoteLineDraft::class.java)
        assertEquals("labor", quoteLinesFromDraft(listOf(old)).single().itemType)
    }
    @Test fun checklistIsReadableAndCannotInjectUnknownValues() {
        assertEquals("Crown loose\nCondition: scratches, dents", watchConditionNotes(" Crown loose ", "scratches|dents|scratches|ignored"))
        assertNull(watchConditionNotes("", "ignored"))
    }
    @Test fun printedCopiesSeparatePrivateAndCustomerInformationAndUseCurrentWebLinks() {
        val job = RepairJobRead("j1", depositCents = 5000, preQuoteCents = 10000, costCents = 25000,
            tenantId = "t", watchId = "w1", jobNumber = "W123", title = "Service", description = "Losing time",
            status = "no_go", priority = "high", customerName = "Avery", createdAt = "2026-11-11", statusToken = "public-token",
            salesperson = "Sam", customerEmail = "avery@example.test")
        val watch = WatchRead("w1", "t", "c", brand = "Seiko", model = "5", serialNumber = "123", movementType = "4R36", conditionNotes = "Scuffed crystal")
        val ctx = JobPrintContext("https://mainspring.test/api/", "Shop", "0400", { it.toString() }, { it })
        val bundle = watchJobBundle(job, ctx, watch)!!
        val (workshop, customer) = intakeTicketCopies(bundle.ticket)
        assertTrue(workshop.rows.contains("Serial" to "123")); assertTrue(workshop.rows.contains("Movement" to "4R36"))
        assertTrue(workshop.rows.contains("Condition notes" to "Scuffed crystal")); assertTrue(workshop.rows.contains("Salesperson" to "Sam"))
        assertTrue(customer.rows.contains("Estimated repair" to "25000")); assertTrue(customer.rows.contains("Estimated balance" to "20000"))
        assertFalse(customer.rows.any { it.first in listOf("Serial", "Email", "Condition notes") })
        assertEquals("https://mainspring.test/jobs/j1", bundle.labels[0].qrText)
        assertEquals("https://mainspring.test/customer-portal/job/watch/public-token", bundle.labels[1].qrText)
        assertEquals("No Go", watchStatusLabel("no_go")); assertEquals("Ready for Collection", watchStatusLabel("awaiting_collection"))
    }
}
