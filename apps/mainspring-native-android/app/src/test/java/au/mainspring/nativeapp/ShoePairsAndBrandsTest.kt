package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.ShoeRead
import au.mainspring.nativeapp.api.ShoeRepairJobRead
import au.mainspring.nativeapp.ui.intakeTicketLabel
import au.mainspring.nativeapp.ui.webPageUrl
import com.google.gson.Gson
import org.junit.Assert.*
import org.junit.Test

class ShoePairsAndBrandsTest {
    @Test fun shoeUpdateBodyTrimsAndKeepsBlanks() {
        val b = shoeUpdateBody(" boots ", "Blundstone", "", " scuffed ")
        assertEquals("boots", b["shoe_type"].asString); assertEquals("", b["color"].asString); assertEquals("scuffed", b["description_notes"].asString)
    }
    @Test fun newPairNeedsTypeBrandOrColour() {
        assertFalse(canAddNewPair(" ", "", "  ")); assertTrue(canAddNewPair("", "Nike", ""))
    }
    @Test fun brandSuggestionsFilterAndHideOnExactMatch() {
        val brands = listOf("Omega", "Rolex", "Tudor", "Rolex Oyster")
        assertEquals(listOf("Rolex", "Rolex Oyster"), watchBrandSuggestions("rol", brands = brands))
        assertEquals(2, watchBrandSuggestions("", 2, brands).size)
        assertTrue(watchBrandSuggestions("rolex", brands = brands).isEmpty())
        assertTrue(WATCH_BRANDS.contains("Rolex") && WATCH_BRANDS.size > 200)
    }
    @Test fun ticketLabelsShowNumbers() {
        assertEquals("Watch 2 · Ticket #1043", intakeTicketLabel(1, "#1043"))
        assertEquals("Watch 1", intakeTicketLabel(0, null)); assertEquals("Watch 3", intakeTicketLabel(2, "  "))
    }
    @Test fun webPageUrlUsesApiOrigin() {
        assertEquals("https://app.example.com/accounts", webPageUrl("https://app.example.com/api/", "accounts"))
        assertEquals("http://10.0.2.2:8000/accounts", webPageUrl("http://10.0.2.2:8000/", "/accounts"))
    }
    @Test fun availableShoesExcludeThoseOnJob() {
        fun shoe(id: String) = ShoeRead(id = id, customerId = "c")
        val json = """{"id":"j","tenant_id":"t","shoe_id":"a","job_number":"1","status_token":"s","title":"T","priority":"normal","status":"awaiting_quote",
            "deposit_cents":0,"cost_cents":0,"quote_approval_token":"q","quote_status":"none","created_at":"2026-01-01T00:00:00Z",
            "shoe":{"id":"a"},"extra_shoes":[{"id":"e1","shoe_id":"b","sort_order":1}]}"""
        val job = Gson().fromJson(json, ShoeRepairJobRead::class.java)
        assertEquals(listOf("c"), availableCustomerShoes(listOf(shoe("a"), shoe("b"), shoe("c")), job).map { it.id })
        assertTrue(availableCustomerShoes(listOf(shoe("a")), null).isEmpty())
    }
}
