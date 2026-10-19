package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.InvoicesScreen
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class InvoicesMergedTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val paths = ConcurrentLinkedQueue<String>()
    private val opened = ConcurrentLinkedQueue<String>()

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?'); paths.add(path)
                val body = when (path) {
                    "/v1/invoices" -> """{"items":[{"id":"w1","tenant_id":"t","repair_job_id":"j1","invoice_number":"INV-W1","status":"unpaid","subtotal_cents":1000,"tax_cents":100,"total_cents":1100,"currency":"AUD","created_at":"2026-10-01T00:00:00Z"}],"total":1,"limit":100,"offset":0}"""
                    "/v1/repair-jobs" -> "[]"
                    "/v1/auto-key-jobs/invoices" -> """[{"id":"m1","auto_key_job_id":"mobile-job-1","invoice_number":"AK-M1","status":"paid","total_cents":5500,"currency":"AUD","created_at":"2026-10-02T00:00:00Z","customer_name":"Mobile Marge"}]"""
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("shop", "manager"); TokenStore.setSessionRole("manager")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun mergesWatchAndMobileFiltersByTypeAndSearchesAndOpensMobile() {
        compose.setContent { MainspringTheme { InvoicesScreen(onOpenInvoice = {}, onOpenMobileInvoice = { opened.add(it) }) } }
        compose.waitUntil(10_000) { compose.onAllNodesWithText("AK-M1").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithText("INV-W1").assertExists()
        compose.onNodeWithText("Mobile").performClick()
        compose.onNodeWithText("INV-W1").assertDoesNotExist()
        compose.onNodeWithText("Watch").performClick()
        compose.onNodeWithText("AK-M1").assertDoesNotExist()
        compose.onNodeWithText("All types").performClick()
        compose.onNodeWithTag("invoices-search").performTextInput("marge")
        compose.onNodeWithText("INV-W1").assertDoesNotExist()
        compose.onNodeWithText("AK-M1").performClick()
        Assert.assertEquals("mobile-job-1", opened.peek())
    }
}
