package au.mainspring.nativeapp

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.MobileQuoteLine
import au.mainspring.nativeapp.api.MobileQuoteOptionCreate
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.MobileFinanceScreen
import au.mainspring.nativeapp.ui.screens.QuoteComposer
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Two-outcome quotes in the native composer and on the job's Financial tab, against a mock server. */
class TwoOutcomeQuoteFlowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val selectBodies = ConcurrentLinkedQueue<String>()
    private var quoteStatus = "sent"
    private val invoiceWrites = java.util.concurrent.atomic.AtomicInteger(0)
    private val options = """"options":[{"key":"A","label":"CAS3","subtotal_cents":36364,"tax_cents":3636,"total_cents":40000},{"key":"B","label":"CAS3++","subtotal_cents":54545,"tax_cents":5455,"total_cents":60000}]"""
    private fun quote(selected: String?) = """{"id":"q1","status":"$quoteStatus","subtotal_cents":54545,"tax_cents":5455,"total_cents":60000,"currency":"AUD","line_items":[
        {"description":"Call-out","quantity":1,"unit_price_cents":10000,"option_key":null},
        {"description":"CAS3 programming","quantity":1,"unit_price_cents":30000,"option_key":"A"},
        {"description":"CAS3++ programming","quantity":1,"unit_price_cents":50000,"option_key":"B"}],$options,"selected_option":${if(selected == null) "null" else "\"$selected\""}}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath
                val json = MockResponse().setHeader("Content-Type", "application/json")
                return when {
                    path == "/v1/auto-key-jobs/job-1/quotes" -> json.setBody("[${quote(null)}]")
                    path == "/v1/auto-key-jobs/job-1/invoices" -> json.setBody("[]")
                    path == "/v1/auto-key-jobs/quotes/q1/select-option" -> { selectBodies.add(request.body.readUtf8()); json.setBody(quote("B")) }
                    path == "/v1/auto-key-jobs/job-1/invoices/from-quote/q1" -> { invoiceWrites.incrementAndGet(); json.setBody("""{"id":"invoice-1","invoice_number":"I-1","status":"unpaid","auto_key_quote_id":"q1","total_cents":60000,"currency":"AUD"}""") }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("quotes", "owner"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun approvedTwoOutcomeQuoteCannotInvoiceUntilOutcomeIsConfirmed() {
        quoteStatus = "approved"
        compose.setContent { MainspringTheme { MobileFinanceScreen("job-1", onBack = {}, embedded = true) } }
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("quote-apply-B").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("mobile-outcome-required").assertExists()
        compose.onNodeWithTag("mobile-quote-invoice-q1").assertIsNotEnabled()
        compose.onAllNodesWithTag("mobile-primary-invoice").assertCountEquals(0)
        Assert.assertEquals(0, invoiceWrites.get())
        compose.onNodeWithTag("quote-apply-B").performScrollTo().performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("mobile-primary-invoice").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("mobile-quote-invoice-q1").assertIsEnabled()
        compose.onNodeWithTag("mobile-primary-invoice").performScrollTo().performClick()
        compose.onNodeWithText("Confirm").performClick()
        compose.waitUntil(10_000) { invoiceWrites.get() == 1 }
    }

    @Test fun viewModelAlsoRejectsUnresolvedOutcomeWithoutSendingAnInvoiceRequest() {
        quoteStatus = "approved"
        val vm = MobileFinanceViewModel("job-1")
        compose.waitUntil(10_000) { vm.state.value.historyChecked }
        vm.createInvoice("q1")
        compose.waitUntil(10_000) { !vm.state.value.busy }
        Assert.assertEquals("Choose which quote option applies before creating an invoice.", vm.state.value.error)
        Assert.assertEquals(0, invoiceWrites.get())
        vm.selectOption("q1", "B")
        compose.waitUntil(10_000) { vm.state.value.quotes.single().selectedOption == "B" && !vm.state.value.busy }
        vm.createInvoice("q1")
        compose.waitUntil(10_000) { vm.state.value.invoices.isNotEmpty() }
        Assert.assertEquals(1, invoiceWrites.get())
    }

    @Test fun technicianConfirmsWhichOutcomeAppliesAndTheCardShowsIt() {
        compose.setContent { MainspringTheme { MobileFinanceScreen("job-1", onBack = {}, embedded = true) } }
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("quote-apply-B").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithText("Which option applies? Pick one once you have seen the vehicle.").assertExists()
        compose.onNodeWithText("CAS3 — 400.00 AUD").assertExists()
        compose.onNodeWithTag("quote-apply-B").performScrollTo().performClick()
        compose.waitUntil(10_000) { selectBodies.isNotEmpty() }
        Assert.assertEquals("B", JsonParser.parseString(selectBodies.peek()).asJsonObject["option"].asString)
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Outcome confirmed").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithText("CAS3++ — 600.00 AUD ✓").assertExists()
        compose.onAllNodesWithTag("quote-apply-A").assertCountEquals(0)
    }

    @Test fun composerBuildsASharedPlusTwoOptionQuote() {
        var saved: Triple<List<MobileQuoteLine>, List<MobileQuoteOptionCreate>, Boolean>? = null
        compose.setContent { MainspringTheme { Column(Modifier.verticalScroll(rememberScrollState())) { QuoteComposer("quote-composer/test", businessAccount = false, enabled = true, catalogue = false, currency = "AUD",
            allowTwoOutcome = true, onSaveOutcomes = { shared, opts, gst, _ -> saved = Triple(shared, opts, gst) }, onSave = { _, _, _ -> Assert.fail("plain save used for a two-outcome quote") }) } } }
        compose.onNodeWithTag("quote-two-outcome").performClick()
        compose.onNodeWithTag("quote-option-a").performTextInput("CAS3")
        compose.onNodeWithTag("quote-option-b").performTextInput("CAS3++")
        fun fillLine(description: String, price: String) {
            compose.onNodeWithText("Description").performTextReplacement(description)
            compose.onNodeWithText("Unit price (\$)").performTextReplacement(price)
        }
        fillLine("Call-out", "100")
        compose.onNodeWithText("Add line").performScrollTo().performClick()
        fillLine("CAS3 programming", "300"); compose.onNodeWithTag("quote-line-option-A").performScrollTo().performClick()
        compose.onNodeWithText("Add line").performScrollTo().performClick()
        fillLine("CAS3++ programming", "500"); compose.onNodeWithTag("quote-line-option-B").performScrollTo().performClick()
        compose.onNodeWithTag("quote-outcome-totals").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("400.00 AUD").assertExists(); compose.onNodeWithText("600.00 AUD").assertExists()
        compose.onNodeWithTag("quote-save").performScrollTo().performClick()
        val (shared, opts, gst) = saved ?: Assert.fail("nothing saved").let { return }
        Assert.assertEquals(listOf("Call-out"), shared.map { it.description })
        Assert.assertEquals(listOf("CAS3", "CAS3++"), opts.map { it.label })
        Assert.assertEquals(listOf(30000), opts[0].lines.map { it.unitCents }); Assert.assertEquals(listOf(50000), opts[1].lines.map { it.unitCents })
        Assert.assertTrue(gst)
    }

    @Test fun saveStaysDisabledUntilBothOptionsHaveAnItem() {
        compose.setContent { MainspringTheme { Column(Modifier.verticalScroll(rememberScrollState())) { QuoteComposer("quote-composer/test2", businessAccount = false, enabled = true, catalogue = false, currency = "AUD",
            allowTwoOutcome = true, onSaveOutcomes = { _, _, _, _ -> }, onSave = { _, _, _ -> }) } } }
        compose.onNodeWithTag("quote-two-outcome").performClick()
        compose.onNodeWithTag("quote-option-a").performTextInput("CAS3")
        compose.onNodeWithTag("quote-option-b").performTextInput("CAS3++")
        compose.onNodeWithText("Description").performTextReplacement("Call-out")
        compose.onNodeWithText("Unit price (\$)").performTextReplacement("100")
        compose.onNodeWithTag("quote-save").performScrollTo().assertIsNotEnabled()
    }
}
