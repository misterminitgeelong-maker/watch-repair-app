package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.ui.screens.bookingStatusLabel
import com.google.gson.Gson
import org.junit.Assert.*
import org.junit.Test

class MobileParityContractsTest {
    @Test fun savedViewsPreserveEveryCockpitFocusAndSanitizeOldValues() {
        assertEquals(16, MOBILE_FOCUS_OPTIONS.size)
        MOBILE_FOCUS_OPTIONS.keys.forEach { key -> assertEquals(key, sanitizeSavedView(MobileSavedView("all", key)).focus) }
        assertNull(sanitizeSavedView(MobileSavedView(focus = "unsupported")).focus)
        val view = SavedJobView("Follow up", statusFilter = "quote_follow_up", sort = "all", technicianId = "tech-1", mobileStatus = "quote_sent", mobileCategory = "pipeline")
        val restored = mobileViewToSaved(Gson().fromJson(Gson().toJson(view), SavedJobView::class.java))
        assertEquals("quote_sent", restored.status); assertEquals("tech-1", restored.technician); assertEquals("pipeline", restored.category)
    }
    @Test fun manualCataloguePriceCarriesItsReferenceAndCalloutContract() {
        val payload = MobileJobCreate("customer", "Remote", null, "normal", "awaiting_quote", null, null, null,
            null, null, null, null, null, null, 1, null, 0,
            costCents = 32500, applySuggestedQuote = false, pricingRefId = "catalogue-id", pricingType = "oem_key", quotedPrice = 325.0, calloutInclusive = true)
        val json = Gson().toJsonTree(payload).asJsonObject
        assertEquals("catalogue-id", json["pricing_ref_id"].asString)
        assertEquals("oem_key", json["pricing_type"].asString)
        assertEquals(32500, json["cost_cents"].asInt)
        assertEquals(325.0, json["quoted_price"].asDouble, 0.0)
        assertTrue(json["callout_inclusive"].asBoolean)
        assertFalse(json["apply_suggested_quote"].asBoolean)
    }
    @Test fun reoffersHaveTheirDeadlineAndHumanDispatchPoolLabel() {
        val row = Gson().fromJson("""{"id":"request","status":"pending","offer_count":3,"offer_expires_at":"2026-11-11T10:00:00Z"}""", BookingRequest::class.java)
        assertEquals(3, row.offerCount); assertEquals("2026-11-11T10:00:00Z", row.offerExpiresAt)
        assertEquals("Moved to Dispatch Pool", bookingStatusLabel("moved_to_pool"))
    }
}
