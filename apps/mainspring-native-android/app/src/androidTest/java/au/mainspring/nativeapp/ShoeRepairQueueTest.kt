package au.mainspring.nativeapp

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipeLeft
import androidx.compose.ui.test.swipeRight
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.screens.RepairQueueScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Shoe lane of the repair queue: lane toggle, advance, skip, undo, progress, empty, error and offline states. */
class ShoeRepairQueueTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<String>()
    private val statuses = linkedMapOf<String, String>()
    private var failMove = false
    private var jobList = true

    private fun job(id: String, status: String) =
        """{"id":"$id","tenant_id":"t","shoe_id":"s-$id","job_number":"S-$id","status_token":"tok","title":"Resole $id","status":"$status","priority":"normal",""" +
            """"deposit_cents":0,"cost_cents":0,"quote_approval_token":"q","quote_status":"none","created_at":"2026-10-08T00:00:00Z"}"""
    private fun moves() = requests.filter { it.startsWith("POST") }

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        statuses.clear(); statuses["1"] = "awaiting_quote"; statuses["2"] = "go_ahead"; failMove = false; jobList = true
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = request.body.readUtf8()
                requests.add("${request.method} $path $body")
                val ok = { json: String -> MockResponse().setHeader("Content-Type", "application/json").setBody(json) }
                if (request.method == "POST" && path.endsWith("/status") && path.startsWith("/v1/shoe-repair-jobs/")) {
                    if (failMove) return MockResponse().setResponseCode(400).setHeader("Content-Type", "application/json").setBody("""{"detail":"Cannot move this job."}""")
                    val id = path.removePrefix("/v1/shoe-repair-jobs/").removeSuffix("/status")
                    statuses[id] = JsonParser.parseString(body).asJsonObject["status"].asString
                    return ok(job(id, statuses.getValue(id)))
                }
                if (path == "/v1/shoe-repair-jobs") return ok(if (jobList) "[" + statuses.map { job(it.key, it.value) }.joinToString(",") + "]" else "[]")
                return ok("[]")
            }
        }; server.start()
        TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("tenant-1", "user-1"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun launch(opened: MutableList<String> = mutableListOf(), online: () -> Boolean = { true }): ShoeRepairQueueViewModel {
        val vm = ShoeRepairQueueViewModel(isOnline = online)
        compose.setContent { RepairQueueScreen(onBack = {}, onOpenJob = {}, onOpenShoeJob = { opened += it }, initialLane = "shoe", shoeViewModel = vm) }
        compose.waitUntil(10_000) { !vm.state.value.loading }
        return vm
    }

    @Test fun advanceButtonMovesTopJobViaShoeStatusEndpoint() {
        val vm = launch()
        compose.onNodeWithTag("queue-progress").assertIsDisplayed()
        compose.onNodeWithTag("queue-advance").performClick()
        compose.waitUntil(10_000) { vm.state.value.advanced == 1 }
        Assert.assertEquals("awaiting_go_ahead", statuses["1"])
        Assert.assertEquals("2", vm.state.value.current?.id)
        Assert.assertTrue(moves().any { it.startsWith("POST /v1/shoe-repair-jobs/1/status") && it.contains("awaiting_go_ahead") })
    }

    @Test fun swipeRightAdvancesAndSwipeLeftSkipsWithoutServerCall() {
        val vm = launch()
        compose.onNodeWithTag("queue-card").performTouchInput { swipeRight() }
        compose.waitUntil(10_000) { vm.state.value.advanced == 1 }
        val callsAfterAdvance = moves().size
        statuses["3"] = "working_on"
        compose.onNodeWithTag("queue-card").performTouchInput { swipeLeft() }
        compose.waitUntil(10_000) { vm.state.value.skipped == 1 }
        Assert.assertEquals(callsAfterAdvance, moves().size)
    }

    @Test fun backIsDisabledAndSkipSendsToEndWithUndo() {
        val vm = launch()
        compose.onNodeWithTag("queue-back").assertIsNotEnabled()
        compose.onNodeWithTag("queue-skip").performClick()
        compose.waitUntil(10_000) { vm.state.value.skipped == 1 }
        Assert.assertEquals(listOf("2", "1"), vm.state.value.queue.map { it.id })
        Assert.assertTrue(moves().isEmpty())
        compose.onNodeWithTag("queue-undo").performClick()
        compose.waitUntil(10_000) { vm.state.value.skipped == 0 }
        Assert.assertEquals(listOf("1", "2"), vm.state.value.queue.map { it.id })
    }

    @Test fun undoSetsPreviousStatusBackOnServer() {
        val vm = launch()
        compose.onNodeWithTag("queue-advance").performClick()
        compose.waitUntil(10_000) { vm.state.value.advanced == 1 }
        compose.onNodeWithTag("queue-undo").assertIsEnabled().performClick()
        compose.waitUntil(10_000) { vm.state.value.advanced == 0 && !vm.state.value.busy }
        Assert.assertEquals("awaiting_quote", statuses["1"])
        Assert.assertEquals("1", vm.state.value.current?.id)
        Assert.assertTrue(moves().last().contains("awaiting_quote"))
        compose.onNodeWithTag("queue-undo").assertIsNotEnabled()
    }

    @Test fun serverErrorKeepsCardAndShowsMessage() {
        failMove = true
        val vm = launch()
        compose.onNodeWithTag("queue-advance").performClick()
        compose.waitUntil(10_000) { vm.state.value.error != null }
        compose.onNodeWithTag("queue-error").assertIsDisplayed()
        compose.onNodeWithText("Cannot move this job.").assertIsDisplayed()
        Assert.assertEquals("1", vm.state.value.current?.id)
        Assert.assertEquals(0, vm.state.value.advanced)
    }

    @Test fun offlineBlocksMovesWithoutCallingServer() {
        val vm = launch(online = { false })
        compose.onNodeWithTag("queue-advance").performClick()
        compose.waitUntil(10_000) { vm.state.value.error == ShoeRepairQueueViewModel.OFFLINE }
        Assert.assertTrue(moves().isEmpty())
    }

    @Test fun emptyQueueShowsEmptyState() {
        jobList = false
        launch()
        compose.onNodeWithTag("queue-empty").assertIsDisplayed()
    }

    @Test fun clearingTheQueueShowsDoneState() {
        statuses.remove("2")
        val vm = launch()
        compose.onNodeWithTag("queue-advance").performClick()
        compose.waitUntil(10_000) { vm.state.value.queue.isEmpty() }
        compose.onNodeWithTag("queue-clear").assertIsDisplayed()
    }

    @Test fun tappingCardOpensShoeJob() {
        val opened = mutableListOf<String>()
        launch(opened)
        compose.onNodeWithTag("queue-card").performClick()
        compose.waitUntil(10_000) { opened.isNotEmpty() }
        Assert.assertEquals(listOf("1"), opened)
    }

    @Test fun laneToggleSwitchesBetweenWatchAndShoe() {
        val watchVm = RepairQueueViewModel(listJobs = { emptyList() })
        val shoeVm = ShoeRepairQueueViewModel()
        compose.setContent { RepairQueueScreen(onBack = {}, onOpenJob = {}, viewModel = watchVm, shoeViewModel = shoeVm) }
        compose.waitUntil(10_000) { !watchVm.state.value.loading }
        compose.onNodeWithTag("queue-empty").assertIsDisplayed()
        compose.onNodeWithTag("queue-lane-shoe").performClick()
        compose.waitUntil(10_000) { !shoeVm.state.value.loading && shoeVm.state.value.total == 2 }
        compose.onNodeWithTag("queue-card").assertIsDisplayed()
        compose.onNodeWithTag("queue-lane-watch").performClick()
        compose.onNodeWithTag("queue-empty").assertIsDisplayed()
    }
}
