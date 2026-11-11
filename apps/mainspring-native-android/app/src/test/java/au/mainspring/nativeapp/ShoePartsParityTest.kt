package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.*
import com.google.gson.Gson
import com.google.gson.JsonParser
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class ShoePartsParityTest {
    @Test fun purchaseAndWarrantyResponseFieldsAreRetained() {
        val shoe = Gson().fromJson("""{"id":"shoe","model_name":"Arizona","size":"41","purchase_date":"2026-10-01","purchase_store":"Geelong","purchase_ref":"RCPT-17","warranty_status":"in_warranty","warranty_expires_on":"2027-10-01"}""", ShoeRead::class.java)
        assertEquals("Arizona", shoe.modelName); assertEquals("41", shoe.size); assertEquals("RCPT-17", shoe.purchaseRef)
        assertEquals("2026-10-01", shoe.purchaseDate); assertEquals("Geelong", shoe.purchaseStore)
        assertEquals("in_warranty", shoe.warrantyStatus); assertEquals("2027-10-01", shoe.warrantyExpiresOn)
    }
    @Test fun shoePatchUsesServerFieldNamesAndExplicitNullForClears() {
        val body = shoeUpdateBody("Sandals", "Birkenstock", "Tan", "Heel worn", ShoePurchaseDetails("Arizona", "41", "01/10/2026", "Geelong", "R17"))
        assertEquals("2026-10-01", body["purchase_date"].asString); assertEquals("Arizona", body["model_name"].asString)
        val cleared = shoeUpdateBody("", "", "", "", ShoePurchaseDetails())
        assertTrue(cleared["purchase_date"].isJsonNull); assertTrue(cleared["purchase_ref"].isJsonNull)
    }
    @Test fun invalidPurchaseDateCannotCreateAnyShopRecords() = runBlocking {
        var writes = 0
        val gateway = object: ShoeIntakeGateway {
            override suspend fun customer(body: CustomerCreate): String { writes++; return "customer" }
            override suspend fun shoe(body: ShoeCreate): String { writes++; return "shoe" }
            override suspend fun job(body: ShoeJobCreate): String { writes++; return "job" }
            override suspend fun link(jobId: String, shoeId: String) { writes++ }
            override suspend fun append(jobId: String, items: List<ShoeItemCreate>) { writes++ }
        }
        try { createShoeIntake(mutableMapOf("name" to "Avery", "count" to "2", "pair.1.purchaseDate" to "31/02/2026"), emptyList(), gateway) { _, _ -> }; fail("Expected invalid date") } catch(_: java.time.format.DateTimeParseException) {}
        assertEquals(0, writes)
    }
    @Test fun intakeCarriesPurchaseFieldsForEachPair() = runBlocking {
        val shoes = mutableListOf<ShoeCreate>()
        val gateway = object: ShoeIntakeGateway {
            override suspend fun customer(body: CustomerCreate) = "customer"
            override suspend fun shoe(body: ShoeCreate): String { shoes += body; return "s${shoes.size}" }
            override suspend fun job(body: ShoeJobCreate) = "job"
            override suspend fun link(jobId: String, shoeId: String) {}
            override suspend fun append(jobId: String, items: List<ShoeItemCreate>) {}
        }
        createShoeIntake(mutableMapOf("name" to "Avery", "count" to "2", "pair.0.model" to "Arizona", "pair.0.size" to "41", "pair.0.purchaseDate" to "01/10/2026", "pair.0.purchaseRef" to "R17", "pair.1.model" to "Boston"), emptyList(), gateway) { _, _ -> }
        assertEquals("Arizona", shoes[0].modelName); assertEquals("2026-10-01", shoes[0].purchaseDate); assertEquals("R17", shoes[0].purchaseRef)
        assertEquals("Boston", shoes[1].modelName); assertNull(shoes[1].purchaseDate)
    }
    @Test fun stockQuantitiesRejectDecimalsNegativesAndOverflow() {
        listOf("1.5", "-1", "1000001", "NaN", "").forEach { raw -> try { partQuantity(raw); fail("Accepted $raw") } catch(_: IllegalArgumentException) {} }
        assertEquals(0, partQuantity("0", true)); assertEquals(1_000_000, partQuantity("1000000"))
    }
    @Test fun transferRequiresDifferentLocationsAndAtLeastOneWholePart() {
        try { partTransfer("mine", "mine", listOf(PartLineInput("SOLE", 1)), ""); fail("same location") } catch(_: IllegalArgumentException) {}
        try { partTransfer("mine", "other", emptyList(), ""); fail("no lines") } catch(_: IllegalArgumentException) {}
        val body = partTransfer("mine", "other", listOf(PartLineInput(" SOLE ", 2)), " Urgent ")
        val json = JsonParser.parseString(Gson().toJson(body)).asJsonObject
        assertEquals("mine", json["from_location_id"].asString); assertEquals("other", json["to_location_id"].asString)
        assertEquals("SOLE", json.getAsJsonArray("lines")[0].asJsonObject["sku"].asString); assertEquals("Urgent", json["note"].asString)
    }
    @Test fun shopSetCountUsesTheAbsoluteCountContract() {
        val body = partAdjustment("mine", "SOLE", "0", "set_count", "Counted empty")
        assertEquals("set_count", body.kind); assertEquals(0, body.quantity)
        try { partAdjustment("mine", "SOLE", "-1", "set_count", ""); fail("Accepted negative stock count") } catch(_: IllegalArgumentException) {}
    }
}
