package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.InvoicesScreen
import au.mainspring.nativeapp.ui.screens.MobileFinanceScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Invoice list "Record payment", mobile invoice "Edit amounts" and the send-channel choice, against a mock server. */
class InvoiceListAndMobileFinanceActionsTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val paymentBodies = ConcurrentLinkedQueue<String>()
    private val patchBodies = ConcurrentLinkedQueue<String>()
    private val sendPaths = ConcurrentLinkedQueue<String>()
    private val mobileInvoice = """{"id":"m1","invoice_number":"AK-M1","status":"unpaid","auto_key_quote_id":null,"total_cents":11000,"currency":"AUD","subtotal_cents":10000,"tax_cents":1000}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath
                val json = MockResponse().setHeader("Content-Type", "application/json")
                return when {
                    path == "/v1/invoices" -> json.setBody("""{"items":[{"id":"w1","tenant_id":"t","repair_job_id":"j1","invoice_number":"INV-W1","status":"unpaid","subtotal_cents":1000,"tax_cents":100,"total_cents":1100,"currency":"AUD","created_at":"2026-10-01T00:00:00Z"}],"total":1,"limit":100,"offset":0}""")
                    path == "/v1/repair-jobs" -> json.setBody("[]")
                    path == "/v1/auto-key-jobs/invoices" -> json.setBody("[]")
                    path == "/v1/invoices/w1" && request.method == "GET" -> json.setBody("""{"invoice":{"id":"w1","tenant_id":"t","repair_job_id":"j1","invoice_number":"INV-W1","status":"unpaid","subtotal_cents":1000,"tax_cents":100,"total_cents":1100,"currency":"AUD","created_at":"2026-10-01T00:00:00Z"},"payments":[]}""")
                    path == "/v1/invoices/w1/payments" -> { paymentBodies.add(request.body.readUtf8()); json.setBody("""{"id":"p1","amount_cents":1100,"currency":"AUD","status":"succeeded","provider":"manual"}""") }
                    path == "/v1/auto-key-jobs/job-1/quotes" -> json.setBody("[]")
                    path == "/v1/auto-key-jobs/job-1/invoices" -> json.setBody("[$mobileInvoice]")
                    path == "/v1/auto-key-jobs/invoices/m1" && request.method == "PATCH" -> { patchBodies.add(request.body.readUtf8()); json.setBody(mobileInvoice.replace("11000", "12000").replace("\"tax_cents\":1000", "\"tax_cents\":2000")) }
                    path == "/v1/auto-key-jobs/invoices/m1/send" -> { sendPaths.add(request.requestUrl!!.query.orEmpty()); json.setBody("""{"invoice":$mobileInvoice,"email_sent":false,"sms_sent":true,"email_skipped_reason":null}""") }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("invoices", "owner"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun invoiceListRecordPaymentSendsTheRemainingBalance() {
        val vm = InvoicesViewModel()
        compose.setContent { MainspringTheme { InvoicesScreen(onOpenInvoice = {}, viewModel = vm) } }
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("invoice-row-pay").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("invoice-row-pay").performClick()
        compose.waitUntil(10_000) { vm.state.value.payTarget != null }
        compose.onNodeWithTag("invoice-row-pay-amount").assertIsDisplayed()
        compose.onNodeWithText("Save").performClick()
        compose.waitUntil(10_000) { paymentBodies.isNotEmpty() }
        Assert.assertEquals(1100, JsonParser.parseString(paymentBodies.peek()).asJsonObject["amount_cents"].asInt)
    }

    @Test fun mobileInvoiceEditAmountsPatchesRecalculatedTotal() {
        compose.setContent { MainspringTheme { MobileFinanceScreen("job-1", onBack = {}, embedded = true) } }
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("mobile-invoice-edit").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("mobile-invoice-edit").performScrollTo().performClick()
        compose.onNodeWithTag("invoice-edit-tax").performTextReplacement("20.00")
        compose.onNodeWithTag("invoice-edit-total").assertTextContains("120.00")
        compose.onNodeWithText("Save").performClick()
        compose.waitUntil(10_000) { patchBodies.isNotEmpty() }
        val body = JsonParser.parseString(patchBodies.peek()).asJsonObject
        Assert.assertEquals(10000, body["subtotal_cents"].asInt); Assert.assertEquals(2000, body["tax_cents"].asInt); Assert.assertEquals(12000, body["total_cents"].asInt)
    }

    @Test fun mobileInvoiceSendUsesTheChosenChannel() {
        compose.setContent { MainspringTheme { MobileFinanceScreen("job-1", onBack = {}, embedded = true) } }
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("mobile-invoice-send").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("mobile-invoice-send").performScrollTo().performClick()
        compose.onNodeWithText("Text only").performClick()
        compose.onNodeWithText("Confirm").performClick()
        compose.waitUntil(10_000) { sendPaths.isNotEmpty() }
        Assert.assertEquals("channel=sms", sendPaths.peek())
    }
}
