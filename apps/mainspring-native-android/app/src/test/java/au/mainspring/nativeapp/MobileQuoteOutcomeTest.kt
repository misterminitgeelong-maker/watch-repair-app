package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.MobileQuote
import au.mainspring.nativeapp.api.MobileQuoteOption
import org.junit.Assert.*
import org.junit.Test

class MobileQuoteOutcomeTest {
    private val options = listOf(MobileQuoteOption("A", "CAS3"), MobileQuoteOption("B", "CAS3++"))
    private fun quote(selected: String? = null) = MobileQuote("q", "approved", 0, 0, 0, "AUD", options = options, selectedOption = selected)
    @Test fun unresolvedOrUnknownOutcomeCannotBeInvoiced() {
        assertTrue(quote().needsOutcomeChoice())
        assertTrue(quote("").needsOutcomeChoice())
        assertTrue(quote("C").needsOutcomeChoice())
    }
    @Test fun validOutcomesAndOrdinaryQuotesCanBeInvoiced() {
        assertFalse(quote("A").needsOutcomeChoice())
        assertFalse(quote("B").needsOutcomeChoice())
        assertFalse(quote().copy(options = emptyList()).needsOutcomeChoice())
        assertFalse(quote().copy(options = null).needsOutcomeChoice())
    }
}
