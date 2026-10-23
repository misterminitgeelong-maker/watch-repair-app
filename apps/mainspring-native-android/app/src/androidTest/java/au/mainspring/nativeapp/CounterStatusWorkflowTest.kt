package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*

class CounterStatusWorkflowTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    private var watchStatus = "working_on"
    private var shoeStatus = "working_on"
    private var watchWrites = 0
    private var shoeWrites = 0
    private var loseResponse = false
    private var failHistoryAfterWrite = false
    private fun job(status: String) = """{"id":"job-1","job_number":"TEST-001","title":"Repair QA","status":"$status","priority":"normal","created_at":"2026-10-08T00:00:00Z","items":[],"quote_status":"not_sent"}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val watch = path.startsWith("/v1/repair-jobs")
                val body = if(path.endsWith("/status")) {
                    val status = JsonParser.parseString(request.body.readUtf8()).asJsonObject["status"].asString
                    if(watch) { watchWrites++; watchStatus = status } else { shoeWrites++; shoeStatus = status }
                    if(loseResponse) return MockResponse().setResponseCode(503).setBody("Unknown status result")
                    job(status)
                } else if(path.endsWith("/job-1")) job(if(watch) watchStatus else shoeStatus)
                else {
                    if(path.endsWith("/status-history") && failHistoryAfterWrite && watchWrites + shoeWrites > 0) return MockResponse().setResponseCode(503).setBody("History temporarily unavailable")
                    "[]"
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("counter-status", "tech"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun watch() = JobDetailViewModel("job-1", server.url("/").toString()).also { compose.waitUntil(10_000) { !it.state.value.loading } }
    private fun shoe() = ShoeJobDetailViewModel("job-1", server.url("/").toString()).also { compose.waitUntil(10_000) { !it.state.value.loading } }
    @Test fun watchDoubleTapAndNoOpCannotDuplicateCompletion() {
        val model = watch(); model.setStatus("completed"); model.setStatus("completed")
        compose.waitUntil(10_000) { !model.state.value.statusBusy && !model.state.value.loading }
        Assert.assertEquals(1, watchWrites); Assert.assertEquals("completed", model.state.value.job!!.status)
        model.setStatus("completed"); Assert.assertEquals(1, watchWrites)
    }
    @Test fun shoeDoubleTapAndNoOpCannotDuplicateCompletion() {
        val model = shoe(); model.setStatus("completed"); model.setStatus("completed")
        compose.waitUntil(10_000) { !model.state.value.statusBusy && !model.state.value.loading }
        Assert.assertEquals(1, shoeWrites); Assert.assertEquals("completed", model.state.value.job!!.status)
        model.setStatus("completed"); Assert.assertEquals(1, shoeWrites)
    }
    @Test fun unknownWatchCompletionRetainsRequestAcrossRecreationAndRequiresReview() {
        loseResponse = true
        val model = watch(); model.setStatus("completed", "Seal checked")
        compose.waitUntil(10_000) { !model.state.value.statusBusy }
        Assert.assertTrue(model.state.value.statusUnknown)
        val restored = watch(); Assert.assertTrue(restored.state.value.statusUnknown); Assert.assertTrue(restored.state.value.statusRequest.contains("Seal checked"))
        restored.setStatus("awaiting_collection"); Assert.assertEquals(1, watchWrites)
        Assert.assertTrue(restored.state.value.statusReviewed); restored.reviewedStatus()
        restored.setStatus("completed"); Assert.assertEquals(1, watchWrites); Assert.assertFalse(restored.state.value.statusUnknown)
    }
    @Test fun unknownShoeCompletionRetainsRequestAcrossRecreationAndRequiresReview() {
        loseResponse = true
        val model = shoe(); model.setStatus("completed", "Soles replaced")
        compose.waitUntil(10_000) { !model.state.value.statusBusy }
        val restored = shoe(); Assert.assertTrue(restored.state.value.statusUnknown); Assert.assertTrue(restored.state.value.statusRequest.contains("Soles replaced"))
        restored.setStatus("awaiting_collection"); Assert.assertEquals(1, shoeWrites)
        restored.reviewedStatus(); restored.setStatus("completed"); Assert.assertEquals(1, shoeWrites)
    }
    @Test fun acknowledgedStatusSurvivesFailedHistoryRefresh() {
        failHistoryAfterWrite = true
        val watch = watch(); watch.setStatus("completed")
        compose.waitUntil(10_000) { !watch.state.value.statusBusy && !watch.state.value.loading }
        Assert.assertEquals("completed", watch.state.value.job!!.status); Assert.assertFalse(watch.state.value.statusUnknown)
        watch.setStatus("completed"); Assert.assertEquals(1, watchWrites)
        val shoe = shoe(); shoe.setStatus("completed")
        compose.waitUntil(10_000) { !shoe.state.value.statusBusy && !shoe.state.value.loading }
        Assert.assertEquals("completed", shoe.state.value.job!!.status); Assert.assertFalse(shoe.state.value.statusUnknown)
        shoe.setStatus("completed"); Assert.assertEquals(1, shoeWrites)
    }
    @Test fun changedServerStatusAndClerkRoleBlockStatusWrites() {
        val watch = watch(); val shoe = shoe()
        watchStatus = "collected"; shoeStatus = "collected"
        watch.setStatus("completed"); shoe.setStatus("completed")
        compose.waitUntil(10_000) { !watch.state.value.statusBusy && !shoe.state.value.statusBusy }
        Assert.assertEquals(0, watchWrites); Assert.assertEquals(0, shoeWrites)
        Assert.assertEquals("collected", watch.state.value.job!!.status); Assert.assertEquals("collected", shoe.state.value.job!!.status)
        TokenStore.setSessionRole("clerk"); watch.setStatus("completed"); shoe.setStatus("completed")
        Assert.assertEquals(0, watchWrites); Assert.assertEquals(0, shoeWrites)
    }
}
