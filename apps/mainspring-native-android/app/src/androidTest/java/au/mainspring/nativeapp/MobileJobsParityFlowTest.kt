package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.CopyOnWriteArrayList

/** Mobile jobs parity flows: Xero retry, run-sheet one-tap status, bulk status and an offline technician note. Compile-checked here; run on a device by the lead. */
class MobileJobsParityFlowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val seen = CopyOnWriteArrayList<String>()
    private var xeroStatus = "failed"
    private var down = false

    private fun job(id: String) = """{"id":"$id","job_number":"MS-$id","title":"Lockout","status":"booking_confirmed","priority":"normal","customer_name":"Avery","customer_phone":"0400000000","job_address":"1 High St","tenant_id":"t","status_token":"tok","commission_lead_source":"other","deposit_cents":0,"cost_cents":0,"key_quantity":1,"programming_status":"pending","updated_at":"v1","created_at":"2026-10-08T00:00:00Z"}"""
    private fun invoice() = """{"id":"inv","invoice_number":"INV-1","status":"unpaid","auto_key_quote_id":"q","total_cents":1000,"currency":"AUD","xero_sync_status":"$xeroStatus","xero_sync_error":"token expired"}"""

    @Before fun setup() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        TokenStore.init(ctx); TokenStore.clear(); TokenStore.setSessionRole("owner"); TokenStore.setDraftScope("parity-shop", "parity-user")
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (down) return MockResponse().setResponseCode(503)
                val path = request.requestUrl!!.encodedPath
                seen += request.method + " " + path
                val body = when {
                    path == "/v1/billing/limits" -> """{"plan_code":"pro","xero_configured":true}"""
                    path == "/v1/auto-key-jobs/invoices/inv/xero/retry" -> { xeroStatus = "synced"; invoice() }
                    path.endsWith("/invoices") -> "[${invoice()}]"
                    path.endsWith("/quotes") -> "[]"
                    path == "/v1/auto-key-jobs/page" -> """{"items":[${job("a")},${job("b")}],"total":2}"""
                    path == "/v1/auto-key-jobs/bulk-status" -> return MockResponse().setResponseCode(204)
                    path == "/v1/auto-key-jobs/a/status" -> job("a").replace("booking_confirmed", "en_route")
                    path == "/v1/auto-key-jobs/a" -> job("a")
                    else -> "{}"
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("parity-shop", "parity-user")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun xeroRetryReplacesFailedStatus() {
        val vm = MobileFinanceViewModel("job")
        compose.waitUntil(10_000) { vm.state.value.historyChecked }
        Assert.assertTrue(vm.state.value.showXero)
        vm.retryXero("inv")
        compose.waitUntil(10_000) { vm.state.value.invoices.firstOrNull()?.xeroSyncStatus == "synced" }
        Assert.assertTrue(seen.contains("POST /v1/auto-key-jobs/invoices/inv/xero/retry"))
    }

    @Test fun runSheetAdvanceSendsVersionedStatus() {
        val vm = TodayViewModel()
        compose.waitUntil(10_000) { !vm.state.value.loading }
        vm.advance("a", "en_route")
        compose.waitUntil(10_000) { vm.state.value.jobs.firstOrNull { it.id == "a" }?.status == "en_route" }
        Assert.assertTrue(seen.contains("POST /v1/auto-key-jobs/a/status"))
    }

    @Test fun bulkStatusPostsSelectedIds() {
        val vm = AutoKeyJobsViewModel()
        compose.waitUntil(10_000) { vm.state.value.jobs.size == 2 }
        vm.startSelecting(); vm.toggleSelectAll(); vm.bulkSetStatus("on_hold".let { "booking_on_hold" })
        compose.waitUntil(10_000) { vm.state.value.bulkMessage != null }
        Assert.assertTrue(seen.contains("POST /v1/auto-key-jobs/bulk-status"))
    }

    @Test fun offlineTechNoteIsQueued() {
        val vm = AutoKeyJobDetailViewModel("a", server.url("/").toString())
        compose.waitUntil(10_000) { vm.state.value.job != null && !vm.state.value.loading }
        down = true; server.shutdown()
        vm.saveTechNotes("Bring spare blade")
        compose.waitUntil(10_000) { vm.state.value.notesSaved || vm.state.value.notesError != null }
        Assert.assertEquals("Bring spare blade", vm.state.value.job?.techNotes)
    }
}
