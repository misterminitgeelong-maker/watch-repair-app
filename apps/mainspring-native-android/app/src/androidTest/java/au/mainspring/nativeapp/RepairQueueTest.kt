package au.mainspring.nativeapp

import androidx.compose.ui.test.click
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipeRight
import androidx.compose.ui.test.swipeLeft
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.screens.RepairQueueScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Repair queue swipe triage: swipe and button advance, back, skip, undo, progress, empty and error states. */
class RepairQueueTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<String>()
    private val statuses = mutableMapOf<String, String>()
    private var failSwipe = false
    private var jobList = true

    private fun job(id: String, status: String) =
        """{"id":"$id","watch_id":"w-$id","tenant_id":"t","job_number":"W-$id","title":"Service $id","status":"$status","priority":"normal","created_at":"2026-10-08T00:00:00Z"}"""
    private fun swipes() = requests.filter { it.startsWith("POST") }

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        statuses.clear(); statuses["1"] = "awaiting_quote"; statuses["2"] = "go_ahead"; failSwipe = false; jobList = true
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = request.body.readUtf8()
                requests.add("${request.method} $path $body")
                val ok = { json: String -> MockResponse().setHeader("Content-Type", "application/json").setBody(json) }
                if (request.method == "POST" && path.endsWith("/queue-swipe")) {
                    if (failSwipe) return MockResponse().setResponseCode(400).setHeader("Content-Type", "application/json").setBody("""{"detail":"Already at first status."}""")
                    val id = path.removePrefix("/v1/repair-jobs/").removeSuffix("/queue-swipe")
                    val dir = JsonParser.parseString(body).asJsonObject["direction"].asString
                    val seq = WATCH_QUEUE_SEQUENCE
                    statuses[id] = seq[seq.indexOf(statuses[id]) + if (dir == "right") 1 else -1]
                    return ok(job(id, statuses.getValue(id)))
                }
                if (path == "/v1/repair-jobs") return ok(if (jobList) "[" + statuses.map { job(it.key, it.value) }.joinToString(",") + "]" else "[]")
                return ok("[]")
            }
        }; server.start()
        TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("tenant-1", "user-1"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun launch(opened: MutableList<String> = mutableListOf()): RepairQueueViewModel {
        val vm = RepairQueueViewModel()
        compose.setContent { au.mainspring.nativeapp.ui.screens.RepairQueueScreen(onBack = {}, onOpenJob = { opened += it }, viewModel = vm) }
        compose.waitUntil(10_000) { !vm.state.value.loading }
        return vm
    }

    @Test fun advanceButtonMovesTopJobAndCountsProgress() {
        val vm = launch()
        compose.onNodeWithTag("queue-progress").assertIsDisplayed()
        compose.onNodeWithTag("queue-advance").performClick()
        compose.waitUntil(10_000) { vm.state.value.advanced == 1 }
        Assert.assertEquals("awaiting_go_ahead", statuses["1"])
        Assert.assertEquals("2", vm.state.value.current?.id)
        Assert.assertTrue(swipes().any { it.startsWith("POST /v1/repair-jobs/1/queue-swipe") && it.contains("\"right\"") })
    }

    @Test fun swipeRightAdvancesAndSwipeLeftStepsBack() {
        val vm = launch()
        compose.onNodeWithTag("queue-card").performTouchInput { swipeRight() }
        compose.waitUntil(10_000) { vm.state.value.advanced == 1 }
        // Job 2 is now on top; swipe left steps it back one status and keeps it on top.
        compose.onNodeWithTag("queue-card").performTouchInput { swipeLeft() }
        compose.waitUntil(10_000) { statuses["2"] == "awaiting_go_ahead" }
        compose.waitUntil(10_000) { !vm.state.value.busy }
        Assert.assertEquals("2", vm.state.value.current?.id)
    }

    @Test fun backOnFirstStepSkipsToEndWithoutServerCall() {
        val vm = launch()
        compose.onNodeWithTag("queue-back").assertIsNotEnabled()
        compose.onNodeWithTag("queue-skip").performClick()
        compose.waitUntil(10_000) { vm.state.value.skipped == 1 }
        Assert.assertEquals(listOf("2", "1"), vm.state.value.queue.map { it.id })
        Assert.assertTrue(swipes().isEmpty())
        compose.onNodeWithTag("queue-undo").performClick()
        compose.waitUntil(10_000) { vm.state.value.skipped == 0 }
        Assert.assertEquals(listOf("1", "2"), vm.state.value.queue.map { it.id })
    }

    @Test fun undoReversesAdvanceOnServerAndRestoresCard() {
        val vm = launch()
        compose.onNodeWithTag("queue-advance").performClick()
        compose.waitUntil(10_000) { vm.state.value.advanced == 1 }
        compose.onNodeWithTag("queue-undo").assertIsEnabled().performClick()
        compose.waitUntil(10_000) { vm.state.value.advanced == 0 && !vm.state.value.busy }
        Assert.assertEquals("awaiting_quote", statuses["1"])
        Assert.assertEquals("1", vm.state.value.current?.id)
        Assert.assertTrue(swipes().last().contains("\"left\""))
        compose.onNodeWithTag("queue-undo").assertIsNotEnabled()
    }

    @Test fun serverErrorKeepsCardAndShowsMessage() {
        failSwipe = true
        val vm = launch()
        compose.onNodeWithTag("queue-advance").performClick()
        compose.waitUntil(10_000) { vm.state.value.error != null }
        compose.onNodeWithTag("queue-error").assertIsDisplayed()
        compose.onNodeWithText("Already at first status.").assertIsDisplayed()
        Assert.assertEquals("1", vm.state.value.current?.id)
        Assert.assertEquals(0, vm.state.value.advanced)
    }

    @Test fun offlineBlocksMovesWithoutCallingServer() {
        val vm = RepairQueueViewModel(isOnline = { false })
        compose.setContent { RepairQueueScreen(onBack = {}, onOpenJob = {}, viewModel = vm) }
        compose.waitUntil(10_000) { !vm.state.value.loading }
        compose.onNodeWithTag("queue-advance").performClick()
        compose.waitUntil(10_000) { vm.state.value.error == RepairQueueViewModel.OFFLINE }
        Assert.assertTrue(swipes().isEmpty())
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

    @Test fun tappingCardOpensJob() {
        val opened = mutableListOf<String>()
        launch(opened)
        // The card now holds buttons and note chips, so tap its title corner rather than its centre.
        compose.onNodeWithTag("queue-card").performTouchInput { click(androidx.compose.ui.geometry.Offset(24f, 24f)) }
        compose.waitUntil(10_000) { opened.isNotEmpty() }
        Assert.assertEquals(listOf("1"), opened)
    }
}
