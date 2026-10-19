package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.AutoKeyJobDetailScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*

class MobileStatusWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var status = "booked"
    private var updated = "2026-10-07T00:00:00Z"
    private var postCode = 200
    private var writes = 0
    private var expected = ""
    private fun job(invoiceCreated: Boolean = false) = """{"id":"job-1","job_number":"M001","title":"Replacement key","status":"$status","updated_at":"$updated","programming_status":"pending","created_at":"2026-10-07T00:00:00Z","invoice_created":$invoiceCreated}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if(request.method == "POST") {
                    writes++; expected = request.getHeader("X-Expected-Updated-At").orEmpty()
                    if(postCode == 409) return MockResponse().setResponseCode(409).setBody("""{"detail":"Job changed"}""")
                    status = JsonParser.parseString(request.body.readUtf8()).asJsonObject["status"].asString
                    updated = "2026-10-07T00:01:00Z"
                    if(postCode == 503) return MockResponse().setResponseCode(503)
                    return MockResponse().setBody(job(true)).setHeader("Content-Type","application/json")
                }
                return MockResponse().setBody(if(request.path.orEmpty().startsWith("/v1/attachments")) "[]" else job()).setHeader("Content-Type","application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("status","operator"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun vm() = AutoKeyJobDetailViewModel("job-1",server.url("/").toString()).also { model -> compose.waitUntil(10_000) { !model.state.value.loading } }
    @Test fun nativeCompletionCarriesVersionAndReportsServerInvoiceOutcome() {
        val model = vm()
        compose.setContent { MainspringTheme { AutoKeyJobDetailScreen("job-1",server.url("/").toString(),{}, {}, {}, {},vm = model) } }
        compose.waitUntil(10_000) { !model.state.value.loading }
        compose.onNodeWithText("More job actions").performScrollTo().performClick()
        compose.onNodeWithText("Change status").performScrollTo().assertIsEnabled()
            .performSemanticsAction(androidx.compose.ui.semantics.SemanticsActions.OnClick) { it() }
        compose.onNodeWithText("Choose status").assertExists()
        compose.onNodeWithText("work_completed").performScrollTo().performClick()
        compose.waitUntil(10_000) { !model.state.value.statusBusy && model.state.value.job!!.status == "work_completed" }
        Assert.assertEquals("2026-10-07T00:00:00Z",expected)
        Assert.assertTrue(model.state.value.statusInfo.orEmpty().contains("invoice was created"))
        model.setStatus("work_completed"); Assert.assertEquals(1,writes)
    }
    @Test fun unknownStatusWriteSurvivesRecreationAndDoesNotReplayCompletion() {
        postCode = 503
        val model = vm(); model.setStatus("work_completed","Keys handed to customer"); compose.waitUntil(10_000) { !model.state.value.statusBusy }
        val restored = vm(); Assert.assertTrue(restored.state.value.statusReviewRequired)
        Assert.assertEquals("work_completed",restored.state.value.requestedStatus); Assert.assertEquals("Keys handed to customer",restored.state.value.requestedNote)
        restored.setStatus("work_completed"); Assert.assertEquals(1,writes)
        restored.reviewedStatus(); restored.setStatus("work_completed")
        Assert.assertEquals(1,writes); Assert.assertEquals("work_completed",restored.state.value.job!!.status)
    }
    @Test fun staleResponseRequiresFreshReadBeforeAnotherStatusRequest() {
        postCode = 409
        val model = vm(); updated = "2026-10-07T00:01:00Z"; model.setStatus("work_completed")
        compose.waitUntil(10_000) { !model.state.value.statusBusy }; model.reviewedStatus(); model.setStatus("work_completed")
        Assert.assertEquals(1,writes)
        model.load(); compose.waitUntil(10_000) { !model.state.value.loading }; model.reviewedStatus(); postCode = 200; model.setStatus("work_completed")
        compose.waitUntil(10_000) { !model.state.value.statusBusy }
        Assert.assertEquals(2,writes); Assert.assertEquals("2026-10-07T00:01:00Z",expected)
    }
    @Test fun counterRoleCannotBypassMobileStatusPermissionThroughViewModel() {
        TokenStore.setSessionRole("clerk")
        val model = vm(); model.setStatus("work_completed")
        Assert.assertEquals(0,writes); Assert.assertEquals("booked",model.state.value.job!!.status)
    }
}
