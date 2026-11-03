package au.mainspring.nativeapp

import org.junit.Assert.*
import org.junit.Test

class QuotePreviewTest {
    private fun draft(price: String,gst: Boolean=true,inclusive: Boolean=true)=QuoteComposerDraft(listOf(QuoteLineDraft("Key",price=price)),gst,inclusive)
    @Test fun inclusiveAustralianGstUsesExactCents() {assertEquals(QuotePreview(1117,112,1229),quotePreview(draft("12.29"),"AUD"))}
    @Test fun inclusiveNewZealandGstUsesFifteenPercent() {assertEquals(QuotePreview(10000,1500,11500),quotePreview(draft("115"),"NZD"))}
    @Test fun exclusiveNewZealandGstIsAdded() {assertEquals(QuotePreview(10000,1500,11500),quotePreview(draft("100",inclusive=false),"NZD"))}
    @Test fun discountsAndFractionalQuantitiesPrecedeTax() {
        val d=QuoteComposerDraft(listOf(QuoteLineDraft("Service","1.5","100","percent","10")),gst=true,inclusive=false)
        assertEquals(QuotePreview(13500,1350,14850),quotePreview(d,"AUD"))
    }
    @Test fun noGstDoesNotAddTax() {assertEquals(QuotePreview(1229,0,1229),quotePreview(draft("12.29",gst=false),"AUD"))}
    @Test fun unsupportedCurrencyDoesNotInventTaxRate() {assertThrows(IllegalArgumentException::class.java) {quotePreview(draft("100"),"USD")}}
}
