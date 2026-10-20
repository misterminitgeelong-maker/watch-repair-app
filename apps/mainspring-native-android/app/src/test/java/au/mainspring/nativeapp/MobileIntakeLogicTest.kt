package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.*
import com.google.gson.Gson
import com.google.gson.JsonParser
import org.junit.Assert.*
import org.junit.Test

class MobileIntakeLogicTest {
    private fun job(make: String? = "Toyota", model: String? = "Hilux", year: Int? = 2019, plate: String? = "ABC123", key: String? = "Flip", blade: String? = "TOY43", chip: String? = "4D", notes: String? = "Check immobiliser") =
        AutoKeyJobRead(id = "j1", tenantId = "t", customerId = "c1", jobNumber = "M001", statusToken = "x", title = "Old", vehicleMake = make, vehicleModel = model, vehicleYear = year,
            registrationPlate = plate, keyType = key, bladeCode = blade, chipType = chip, techNotes = notes, keyQuantity = 1, programmingStatus = "not_required", priority = "normal", status = "completed",
            depositCents = 0, costCents = 0, createdAt = "2026-01-01", commissionLeadSource = "shop")

    @Test fun pricingTierFollowsLinkedBusinessAccount() { assertEquals("retail", pricingTierFor("")); assertEquals("b2b", pricingTierFor("acct-1")) }

    @Test fun fallbackMatchesServerCatalogueForRetailAndB2b() {
        val retail = fallbackQuoteSuggestion("All Keys Lost", 1, "retail", emptyList())
        assertEquals(44900, retail.lines.single().totalPriceCents); assertEquals(49390, retail.totalCents); assertTrue(retail.estimated)
        val b2b = fallbackQuoteSuggestion("All Keys Lost", 1, "b2b", emptyList())
        assertEquals(35920, b2b.lines.single().unitPriceCents)
    }

    @Test fun fallbackScalesByQuantityAndAddsExtraPresets() {
        val s = fallbackQuoteSuggestion("Duplicate Key", 3, "retail", listOf("Diagnostic", "Not a preset"))
        assertEquals(2, s.lines.size); assertEquals(3 * 8900, s.lines[0].totalPriceCents); assertEquals(15900, s.lines[1].totalPriceCents)
        assertEquals(Math.round((3 * 8900 + 15900) * 0.10).toInt() + 3 * 8900 + 15900, s.totalCents)
    }

    @Test fun unknownJobTypeUsesGenericLineLikeTheServer() {
        val s = fallbackQuoteSuggestion(null, 0, "tier2", emptyList())
        assertEquals("Mobile key service", s.lines.single().description); assertEquals(10500, s.lines.single().unitPriceCents); assertEquals(1.0, s.lines.single().quantity, 0.0)
    }

    @Test fun serverSuggestionParsesAndIsNotAnEstimate() {
        val json = """{"pricing_tier":"b2b","total_cents":3300,"subtotal_cents":3000,"tax_cents":300,"line_items":[{"id":"0","description":"Key cutting","quantity":1,"unit_price_cents":3000,"total_price_cents":3000}]}"""
        val s = Gson().fromJson(json, QuoteSuggestionRead::class.java).toSuggested("retail")
        assertFalse(s.estimated); assertEquals(3300, s.totalCents); assertEquals("b2b", s.tier); assertEquals("Key cutting", s.lines.single().description)
    }

    @Test fun extraServicesRoundTripAndDropEmptyRows() {
        val rows = listOf(ExtraService("Diagnostic", ""), ExtraService("", "  Re-shell  "), ExtraService("", " "))
        assertEquals(rows, decodeExtraServices(encodeExtraServices(rows)))
        val payload = extraServicesPayload(rows)
        assertEquals(2, payload.size); assertEquals("Diagnostic", payload[0].preset); assertNull(payload[0].custom); assertEquals("Re-shell", payload[1].custom)
        assertEquals(listOf("Diagnostic"), extraPresets(rows))
        assertTrue(decodeExtraServices("not json").isEmpty()); assertTrue(decodeExtraServices("").isEmpty())
    }

    @Test fun jobCreateSerialisesNewFieldsAndOmitsBlanks() {
        val body = MobileJobCreate("c1", "Key", null, "normal", "awaiting_quote", null, null, "Diagnostic", null, null, null, null, null, null, 1, null, 0,
            bladeCode = "HU66", chipType = "ID46", salesperson = "Sam", costCents = 1000, applySuggestedQuote = true, additionalServices = extraServicesPayload(listOf(ExtraService("Diagnostic", ""))), commissionLeadSource = "shop")
        val json = JsonParser.parseString(Gson().toJson(body)).asJsonObject
        assertEquals("HU66", json["blade_code"].asString); assertEquals("ID46", json["chip_type"].asString); assertEquals("Sam", json["salesperson"].asString)
        assertEquals(1000, json["cost_cents"].asInt); assertTrue(json["apply_suggested_quote"].asBoolean); assertEquals("shop", json["commission_lead_source"].asString)
        assertEquals("Diagnostic", json["additional_services"].asJsonArray[0].asJsonObject["preset"].asString)
        assertFalse(json["additional_services"].asJsonArray[0].asJsonObject.has("custom"))
    }

    @Test fun lastVehicleFieldsSkipMissingValuesAndSummaryReads() {
        val fields = lastVehicleFields(job(plate = null, notes = " "))
        assertEquals("Toyota", fields["make"]); assertEquals("2019", fields["year"]); assertEquals("TOY43", fields["blade"]); assertEquals("4D", fields["chip"])
        assertFalse(fields.containsKey("plate")); assertFalse(fields.containsKey("notes"))
        assertEquals("Toyota 2019 Hilux · ABC123 · Flip", lastVehicleSummary(job()))
        assertTrue(hasLastVehicle(job())); assertFalse(hasLastVehicle(job(make = null, model = " "))); assertFalse(hasLastVehicle(null))
    }

    @Test fun specMatchFillsKeyFieldsAndKeepsTypedYear() {
        val m = VehicleKeySpecMatch(vehicleMake = "Holden", vehicleModel = "Commodore", yearFrom = 2006, keyType = "Flip", chipType = "ID46", techNotes = "PIN needed", suggestedBladeCode = "HU100")
        val typed = specMatchFields(mapOf("year" to "2010"), m)
        assertFalse(typed.containsKey("year")); assertEquals("Holden", typed["make"]); assertEquals("HU100", typed["blade"]); assertEquals("ID46", typed["chip"]); assertEquals("PIN needed", typed["notes"])
        assertEquals("2006", specMatchFields(emptyMap(), m)["year"])
        assertFalse(specMatchFields(emptyMap(), VehicleKeySpecMatch(vehicleMake = "Kia", vehicleModel = "Rio")).containsKey("blade"))
    }

    @Test fun specResponseParsesAndBlanksPreferPrimaryCode() {
        val json = """{"matches":[{"score":90,"label":"Kia Rio","vehicle_make":"Kia","vehicle_model":"Rio","key_blanks":[{"primary_code":"KIA3"},{"blank_reference":"HY20"},{}],"suggested_blade_code":"KIA3"}]}"""
        val m = Gson().fromJson(json, VehicleKeySpecSearch::class.java).matches.single()
        assertEquals("KIA3, HY20", specBlanks(m)); assertEquals("KIA3", specBlanks(m.copy(keyBlanks = null)))
    }

    @Test fun lookupGates() {
        assertFalse(specLookupReady("T", "")); assertTrue(specLookupReady("To", "")); assertTrue(specLookupReady("", "Hi"))
        assertFalse(addressLookupReady("1 Ma ")); assertTrue(addressLookupReady("1 Mai"))
    }

    @Test fun commissionOptionsMatchWebAndOnSiteTypesNeedAnAddress() {
        assertEquals(listOf("shop", "tech_sourced", "minit_sourced", "shop_referred"), MOBILE_COMMISSION_SOURCES.map { it.first })
        assertTrue(MOBILE_COMMISSION_SOURCES.any { it.first == DEFAULT_COMMISSION_SOURCE })
        assertTrue(MOBILE_ON_SITE_JOB_TYPES.all { it in MOBILE_JOB_TYPES }); assertFalse("Duplicate Key" in MOBILE_ON_SITE_JOB_TYPES)
    }
}
