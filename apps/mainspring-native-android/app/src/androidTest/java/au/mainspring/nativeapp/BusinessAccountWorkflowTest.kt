package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.BusinessAccountScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*

class BusinessAccountWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var writes = 0
    private var previewRequests = 0
    private var failInvoice = false
    private var invoiceBody = ""
    private var linked = false
    private var invoiceSaved = false
    private val invoice = """{"id":"invoice-1","invoice_number":"B2B-00001","period_year":2026,"period_month":9,"status":"unpaid","subtotal_cents":24750,"tax_cents":2475,"total_cents":27225,"currency":"AUD","lines":[]}"""
    private fun account() = """{"id":"account-1","name":"Avery Fleet","payment_terms_days":30,"is_active":true,"customer_ids":${if(linked) "[\"customer-1\"]" else "[]"}}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = when {
                    path == "/v1/customer-accounts/account-1" -> account()
                    path == "/v1/customer-accounts/account-1/statement" -> { previewRequests++
                        Assert.assertTrue(request.path!!.contains("period_year=2026")); Assert.assertTrue(request.path!!.contains("period_month=9"))
                        """{"period_year":2026,"period_month":9,"subtotal_cents":24750,"lines":[{"source_type":"watch","source_job_id":"job-1","job_number":"W001","description":"Repair","amount_cents":24750}]}""" }
                    path == "/v1/customer-accounts/account-1/invoices" -> if(invoiceSaved) "[$invoice]" else "[]"
                    path == "/v1/customer-accounts/account-1/invoices/monthly" -> {
                        writes++; invoiceBody = request.body.readUtf8()
                        if(failInvoice) return MockResponse().setResponseCode(503)
                        invoiceSaved = true; invoice
                    }
                    path == "/v1/customers" -> """[{"id":"customer-1","full_name":"Avery Customer"}]"""
                    path == "/v1/customers/customer-1" -> """{"id":"customer-1","full_name":"Avery Customer"}"""
                    path == "/v1/customer-accounts/account-1/customers" -> { Assert.assertEquals("customer-1", JsonParser.parseString(request.body.readUtf8()).asJsonObject["customer_id"].asString); linked = true; account() }
                    path == "/v1/customer-accounts/account-1/customers/customer-1" -> { linked = false; return MockResponse().setResponseCode(204) }
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("fleet", "manager"); TokenStore.setSessionRole("manager")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun vm(): BusinessAccountViewModel = BusinessAccountViewModel("account-1").also { model -> compose.waitUntil(10_000) { !model.state.value.loading } }

    @Test fun monthlyInvoiceUsesPreviewPeriodAndExactTaxAfterConfirmation() {
        val model = vm(); model.setPeriod("09/2026"); model.setTax("24.75")
        compose.setContent { MainspringTheme { BusinessAccountScreen("account-1", {}, {}, { _,_ -> }, model) } }
        compose.onNodeWithText("Preview statement").performScrollTo()
        compose.waitUntil(10_000) {compose.onAllNodes(hasText("Preview statement") and isEnabled()).fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithText("Preview statement").performClick()
        compose.waitUntil(10_000) { model.state.value.statement != null }
        compose.onNodeWithText("Generate monthly invoice").performScrollTo().performClick(); Assert.assertEquals(0, writes)
        compose.onNodeWithText("Confirm invoice").performClick()
        compose.waitUntil(10_000) { model.state.value.invoices.size == 1 }
        val body = JsonParser.parseString(invoiceBody).asJsonObject
        Assert.assertEquals(2475, body["tax_cents"].asInt); Assert.assertEquals(9, body["period_month"].asInt)
        model.generate(); compose.waitUntil(10_000) { !model.state.value.busy }; Assert.assertEquals(1, writes)
    }
    @Test fun unknownInvoiceRetainsPeriodAndTaxAndBlocksBlindRetry() {
        failInvoice = true
        val model = vm(); model.setPeriod("09/2026"); model.setTax("24.75"); model.preview()
        compose.waitUntil(10_000) { !model.state.value.busy }; model.generate()
        compose.waitUntil(10_000) { !model.state.value.busy }
        val restored = vm(); Assert.assertTrue(restored.state.value.uncertain)
        Assert.assertEquals("09/2026", restored.state.value.period); Assert.assertEquals("24.75", restored.state.value.tax)
        restored.generate(); Assert.assertEquals(1, writes)
        restored.setPeriod("10/2026"); Assert.assertEquals("09/2026", restored.state.value.period)
    }
    @Test fun membershipChangesRequireConfirmationAndReloadServerMembership() {
        val model = vm()
        compose.setContent { MainspringTheme { BusinessAccountScreen("account-1", {}, {}, { _,_ -> }, model) } }
        compose.onNodeWithText("Search customers").performScrollTo()
        // The screen refreshes on resume; wait for its real enabled state before tapping.
        compose.waitUntil(10_000) {compose.onAllNodes(hasText("Search customers") and isEnabled()).fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithText("Search customers").performClick()
        compose.waitUntil(10_000) { model.state.value.customers.isNotEmpty() }
        compose.onNodeWithText("Link Avery Customer").performScrollTo().performClick(); Assert.assertFalse(linked)
        compose.onNodeWithText("Confirm membership change").performClick()
        compose.waitUntil(10_000) { !model.state.value.busy }; Assert.assertTrue(linked)
        compose.onNodeWithText("Remove").performScrollTo().performClick(); Assert.assertTrue(linked)
        compose.onNodeWithText("Confirm membership change").performClick()
        compose.waitUntil(10_000) { !model.state.value.busy }; Assert.assertFalse(linked)
        Assert.assertTrue(model.state.value.account!!.customerIds.isEmpty())
    }
    @Test fun invalidMonthMakesNoStatementOrInvoiceRequests() {
        val model = vm(); model.setPeriod("13/2026"); model.preview()
        compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertEquals(0, previewRequests); Assert.assertEquals(0, writes)
        Assert.assertTrue(model.state.value.error.orEmpty().contains("valid billing month"))
    }
}
