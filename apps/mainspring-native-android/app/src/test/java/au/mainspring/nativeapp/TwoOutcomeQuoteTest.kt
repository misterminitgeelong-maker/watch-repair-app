package au.mainspring.nativeapp
import au.mainspring.nativeapp.api.*
import com.google.gson.Gson
import kotlinx.coroutines.runBlocking
import org.junit.*

/** Two-outcome (A/B) quotes, mirroring the web POS and `backend/app/auto_key_quote_options.py`. */
class TwoOutcomeQuoteTest {
 private fun draft() = QuoteComposerDraft(
  lines = listOf(
   QuoteLineDraft("Call-out", "1", "100"),
   QuoteLineDraft("CAS3 programming", "1", "300", option = "A"),
   QuoteLineDraft("CAS3++ programming", "1", "500", option = "B")),
  twoOutcome = true, labelA = "CAS3", labelB = "CAS3++")

 @Test fun splitSeparatesSharedLinesFromEachOption() {
  val split = quoteOutcomeSplit(draft())
  Assert.assertEquals(listOf("Call-out"), split.shared.map { it.description })
  Assert.assertEquals(listOf("CAS3", "CAS3++"), split.options.map { it.label })
  Assert.assertEquals(30000, split.options[0].lines.single().unitCents)
  Assert.assertEquals(50000, split.options[1].lines.single().unitCents)
 }
 @Test fun bothOptionsNeedANameAndAnItemOfTheirOwn() {
  try { quoteOutcomeSplit(draft().copy(labelB = " ")); Assert.fail("Unnamed option accepted") } catch(_: IllegalArgumentException) {}
  try { quoteOutcomeSplit(draft().copy(lines = draft().lines.filter { it.option != "B" })); Assert.fail("Empty option accepted") } catch(_: IllegalArgumentException) {}
 }
 @Test fun previewTotalsCountSharedLinesInBothOptions() {
  val previews = quoteOutcomePreviews(draft(), "AUD")
  Assert.assertEquals(40000L, previews.getValue("A").total)
  Assert.assertEquals(60000L, previews.getValue("B").total)
 }
 @Test fun requestBodyMatchesTheWebPayload() {
  val split = quoteOutcomeSplit(draft())
  val json = Gson().toJsonTree(MobileQuoteCreate(split.shared, true, true, split.options)).asJsonObject
  Assert.assertEquals(1, json.getAsJsonArray("line_items").size())
  val options = json.getAsJsonArray("options")
  Assert.assertEquals("CAS3", options[0].asJsonObject["label"].asString)
  Assert.assertEquals(30000, options[0].asJsonObject.getAsJsonArray("line_items")[0].asJsonObject["unit_price_cents"].asInt)
  // an ordinary quote must not send an options key at all
  Assert.assertFalse(Gson().toJsonTree(MobileQuoteCreate(split.shared, true, true)).asJsonObject.has("options"))
 }
 @Test fun readsServerQuoteWithOptionsAndSelection() {
  val quote = Gson().fromJson("""{"id":"q1","status":"sent","subtotal_cents":1,"tax_cents":0,"total_cents":60000,"currency":"AUD",
   "line_items":[{"description":"CAS3 programming","quantity":1,"unit_price_cents":30000,"option_key":"A"}],
   "options":[{"key":"A","label":"CAS3","subtotal_cents":36364,"tax_cents":3636,"total_cents":40000},{"key":"B","label":"CAS3++","subtotal_cents":54545,"tax_cents":5455,"total_cents":60000}],
   "selected_option":"B"}""", MobileQuote::class.java)
  Assert.assertEquals("A", quote.lines.single().optionKey)
  Assert.assertEquals(listOf("CAS3", "CAS3++"), quote.options!!.map { it.label })
  Assert.assertEquals("B", quote.selectedOption)
 }
 @Test fun anOldSavedDraftWithoutOutcomeFieldsStillLoads() {
  val old = Gson().fromJson("""{"lines":[{"description":"Key","quantity":"1","price":"50","discountType":"none","discount":""}],"gst":true,"inclusive":true,"gstChoiceMade":false}""", QuoteComposerDraft::class.java)
  Assert.assertFalse(old.twoOutcome); Assert.assertNull(old.lines.single().option)
  Assert.assertEquals("Key", quoteLinesFromDraft(old.lines).single().description)
 }

 private class Fake: CounterSaleGateway {
  var quoteBody: MobileQuoteCreate? = null; var invoices = 0
  override suspend fun customer(body: CustomerCreate) = "c1"
  override suspend fun job(body: MobileJobCreate) = "j1"
  override suspend fun quote(jobId: String, body: MobileQuoteCreate): String { quoteBody = body; return "q1" }
  override suspend fun invoice(jobId: String, quoteId: String): String { invoices++; return "i1" }
  override suspend fun complete(jobId: String) {}
 }
 private fun request(mode: String, split: QuoteOutcomeSplit) = CounterSaleRequest("", "Avery", "", "", null, mode, split.shared, true, true, "Quote", null, split.options)
 @Test fun counterQuoteSendsBothOptionsAndNeverInvoices() = runBlocking {
  val gateway = Fake()
  createCounterSale(request("quote", quoteOutcomeSplit(draft())), mutableMapOf(), gateway) { _, _ -> }
  Assert.assertEquals(2, gateway.quoteBody!!.options!!.size); Assert.assertEquals(1, gateway.quoteBody!!.lines.size); Assert.assertEquals(0, gateway.invoices)
 }
 @Test fun twoOutcomesAreRefusedForACounterSale() {
  try { runBlocking { createCounterSale(request("sale", quoteOutcomeSplit(draft())), mutableMapOf(), Fake()) { _, _ -> } }; Assert.fail("Two outcomes accepted for a sale") } catch(_: IllegalArgumentException) {}
 }
 @Test fun anOptionsOnlyQuoteWithNoSharedLinesIsAccepted() = runBlocking {
  val noShared = draft().copy(lines = draft().lines.filter { it.option != null })
  val gateway = Fake()
  createCounterSale(request("quote", quoteOutcomeSplit(noShared)), mutableMapOf(), gateway) { _, _ -> }
  Assert.assertTrue(gateway.quoteBody!!.lines.isEmpty()); Assert.assertEquals(2, gateway.quoteBody!!.options!!.size)
 }
}
