package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.DispatchPoolScreen
import okhttp3.mockwebserver.*
import org.junit.*

class DispatchWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var claimCode = 200
    private var writes = 0
    private val pool = """[{"id":"pool-1","customer_name":"Avery","job_address":"10 Test Street","vehicle_make":"Toyota","ring":1,"created_at":"2026-10-07T00:00:00Z"}]"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when(request.path) {
                "/v1/pool" -> MockResponse().setHeader("Content-Type", "application/json").setBody(pool)
                "/v1/pool/pool-1/claim" -> {
                    writes++
                    MockResponse().setResponseCode(claimCode).setHeader("Content-Type", "application/json")
                        .setBody(if(claimCode == 200) """{"auto_key_job_id":"job-1","job_number":"M001"}""" else """{"detail":"Job has already been claimed."}""")
                }
                else -> MockResponse().setResponseCode(404)
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("dispatch", "operator")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun claimRequiresConfirmationAndOpensAcknowledgedJob() {
        val vm = DispatchPoolViewModel(); var opened = ""
        compose.setContent { MainspringTheme { DispatchPoolScreen({}, { opened = it }, {}, vm) } }
        compose.waitUntil(10_000) { !vm.state.value.loading }
        compose.onNodeWithText("Claim job").performClick()
        Assert.assertEquals(0, writes)
        compose.onNodeWithText("Confirm claim").performClick()
        compose.waitUntil(10_000) { vm.state.value.claimed != null }
        compose.onNodeWithText("Open claimed job").performClick()
        Assert.assertEquals("job-1", opened); Assert.assertEquals(1, writes)
        vm.claim("pool-1"); Assert.assertEquals(1, writes)
    }

    @Test fun unknownClaimSurvivesRecreationAndRequiresFreshReview() {
        claimCode = 503
        val vm = DispatchPoolViewModel()
        compose.waitUntil(10_000) { vm.state.value.historyChecked }
        vm.claim("pool-1"); compose.waitUntil(10_000) { !vm.state.value.busy }
        Assert.assertEquals("pool-1", vm.state.value.unresolvedId)
        val restored = DispatchPoolViewModel()
        restored.claim("pool-1"); Assert.assertEquals(1, writes)
        compose.waitUntil(10_000) { restored.state.value.historyChecked }
        compose.setContent { MainspringTheme { DispatchPoolScreen({}, {}, {}, restored) } }
        compose.waitUntil(10_000) {compose.onAllNodes(hasText("I have reviewed the job board") and isEnabled()).fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithText("I have reviewed the job board").performClick()
        compose.onNodeWithText("Claim job").performClick(); compose.onNodeWithText("Confirm claim").performClick()
        compose.waitUntil(10_000) { !restored.state.value.busy }
        Assert.assertEquals(2, writes)
    }

    @Test fun competingClaimShowsServerConflictWithoutCreatingAnotherJob() {
        claimCode = 409
        val vm = DispatchPoolViewModel()
        compose.waitUntil(10_000) { vm.state.value.historyChecked }
        vm.claim("pool-1"); compose.waitUntil(10_000) { !vm.state.value.busy }
        Assert.assertNull(vm.state.value.claimed)
        Assert.assertTrue(vm.state.value.error.orEmpty().contains("already been claimed"))
        Assert.assertEquals("", vm.state.value.unresolvedId)
        Assert.assertEquals(1, writes)
    }
}
