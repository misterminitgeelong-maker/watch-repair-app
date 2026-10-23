package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class DatabaseTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    private val paths = ConcurrentLinkedQueue<String>()
    private val uploads = ConcurrentLinkedQueue<String>()
    private val gst = """{"watch":{"invoice_count":2,"subtotal_cents":10000,"gst_cents":1000,"total_cents":11000},"mobile":{"invoice_count":1,"subtotal_cents":5000,"gst_cents":500,"total_cents":5500},"combined":{"invoice_count":3,"subtotal_cents":15000,"gst_cents":1500,"total_cents":16500}}"""
    private val importBody = """{"import_id":"i1","imported":1,"skipped":1,"customers_created":1,"total_rows":2,"skipped_reasons":{"missing customer":1},"dry_run":%s}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty()
                paths.add(request.method + " " + path)
                val json = { body: String -> MockResponse().setHeader("Content-Type", "application/json").setBody(body) }
                return when {
                    path.startsWith("/v1/reports/gst-summary") -> json(gst)
                    path.startsWith("/v1/reports/export/jobs") -> MockResponse().setHeader("Content-Type", "text/csv").setBody("a,b\n1,2\n")
                    path.startsWith("/v1/auth/export-my-data") -> json("""{"customers":[]}""")
                    path.startsWith("/v1/import/csv") -> {
                        uploads.add(request.body.readUtf8())
                        json(importBody.format(if(path.contains("dry_run=true")) "true" else "false"))
                    }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("db", "owner"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun gstSummaryLoadsForSelectedPeriod() {
        val model = DatabaseViewModel(); compose.waitUntil(10_000) { model.state.value.gst != null }
        Assert.assertEquals(1500L, model.state.value.gst!!.combined!!.gstCents)
        model.selectPeriod("quarter"); compose.waitUntil(10_000) { paths.any { it.contains("period=quarter") } }
    }

    @Test fun exportsDownloadBytes() {
        val model = DatabaseViewModel()
        val csv = runBlocking { model.download(DatabaseExport.Jobs) }
        Assert.assertEquals("a,b\n1,2\n", String(csv))
        val json = runBlocking { model.download(DatabaseExport.MyData) }
        Assert.assertTrue(String(json).contains("customers"))
    }

    @Test fun importPreviewCountsRowsAndUploadsMultipart() {
        val model = DatabaseViewModel(); compose.waitUntil(10_000) { !model.state.value.gstLoading }
        model.selectTarget("shoe")
        model.choose("history.csv", "customer,phone\n\"Sam\nSmith\",123\nJo,456\n\n".toByteArray())
        Assert.assertEquals(2, model.state.value.picked!!.rowCount)
        model.runImport(dryRun = true); compose.waitUntil(10_000) { model.state.value.importResult != null }
        Assert.assertTrue(model.state.value.importResult!!.dryRun)
        Assert.assertEquals(1, model.state.value.importResult!!.skippedReasons!!["missing customer"])
        Assert.assertTrue(paths.any { it.startsWith("POST /v1/import/csv") && it.contains("import_target=shoe") && it.contains("dry_run=true") })
        Assert.assertNotNull("file kept for the real run", model.state.value.picked)
        model.runImport(dryRun = false); compose.waitUntil(10_000) { model.state.value.importResult?.dryRun == false }
        Assert.assertNull(model.state.value.picked)
        Assert.assertTrue(uploads.first(), uploads.first().contains("filename=\"history.csv\""))
    }

    @Test fun clerkIsBlocked() {
        TokenStore.setSessionRole("clerk")
        val model = DatabaseViewModel()
        Assert.assertFalse(model.state.value.allowed)
        Assert.assertTrue(paths.isEmpty())
    }
}
