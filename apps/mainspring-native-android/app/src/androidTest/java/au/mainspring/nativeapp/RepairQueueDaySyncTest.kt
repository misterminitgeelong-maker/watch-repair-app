package au.mainspring.nativeapp

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.screens.RepairQueueScreen
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Repair queue day progress (me/repair-queue-day), notes, log work, claim, no-update and filters against a mock server. */
class RepairQueueDaySyncTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<String>()
    private var savedDay = """{"shop_date":"2026-10-20","mode":"watch","done_ids":["1"],"queue_order_ids":["2","1"],"stats":{"advanced":1,"checkedIn":0,"skipped":0}}"""

    private fun job(id: String, status: String, priority: String = "normal") =
        """{"id":"$id","watch_id":"w-$id","tenant_id":"t","job_number":"W-$id","title":"Service $id","status":"$status","priority":"$priority","created_at":"2026-10-08T00:00:00Z"}"""
    private fun sent(prefix: String) = requests.filter { it.startsWith(prefix) }

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = request.body.readUtf8()
                requests.add("${request.method} $path $body")
                val ok = { json: String -> MockResponse().setHeader("Content-Type", "application/json").setBody(json) }
                return when {
                    request.method == "GET" && path == "/v1/me/repair-queue-day" -> ok(savedDay)
                    request.method == "PUT" && path == "/v1/me/repair-queue-day" -> { savedDay = body; ok(body) }
                    request.method == "DELETE" && path == "/v1/me/repair-queue-day" -> MockResponse().setResponseCode(204)
                    request.method == "GET" && path == "/v1/repair-jobs" -> ok("[" + listOf(job("1", "awaiting_quote"), job("2", "go_ahead", "urgent"), job("3", "working_on")).joinToString(",") + "]")
                    request.method == "POST" && path.endsWith("/note") -> ok("{}")
                    request.method == "POST" && path == "/v1/work-logs" -> ok("""{"id":"l1","note":"x","minutes_spent":5,"created_at":"2026-10-20T00:00:00Z"}""")
                    request.method == "POST" && path.endsWith("/claim") -> ok(job("2", "go_ahead", "urgent").replace("}", ""","claimed_by_user_id":"user-1","claimed_by_name":"Me"}"""))
                    request.method == "POST" && path.endsWith("/queue-swipe") -> ok(job(path.split('/')[3], "go_ahead"))
                    else -> ok("[]")
                }
            }
        }; server.start()
        TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("tenant-1", "user-1"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun launch(): RepairQueueViewModel {
        val vm = RepairQueueViewModel()
        compose.setContent { RepairQueueScreen(onBack = {}, onOpenJob = {}, viewModel = vm) }
        compose.waitUntil(10_000) { !vm.state.value.loading }
        return vm
    }

    @Test fun reopeningRestoresSavedProgressAndOrder() {
        val vm = launch()
        Assert.assertEquals(listOf("2", "3"), vm.state.value.queue.map { it.id })
        Assert.assertEquals(1, vm.state.value.doneCount)
        compose.onNodeWithTag("queue-progress").assertIsDisplayed()
    }

    @Test fun advancingSavesProgressBackToTheServer() {
        val vm = launch()
        compose.onNodeWithTag("queue-advance").performClick()
        compose.waitUntil(10_000) { sent("PUT /v1/me/repair-queue-day").isNotEmpty() }
        Assert.assertTrue(sent("PUT /v1/me/repair-queue-day").last().contains("\"2\""))
        Assert.assertEquals(2, vm.state.value.doneCount)
    }

    @Test fun noteDialogPostsTheNote() {
        launch()
        compose.onNodeWithTag("queue-note").performClick()
        compose.onNodeWithTag("queue-dialog-text").performTextInput("Parts ordered")
        compose.onNodeWithTag("queue-dialog-confirm").performClick()
        compose.waitUntil(10_000) { sent("POST /v1/repair-jobs/2/note").isNotEmpty() }
        Assert.assertTrue(sent("POST /v1/repair-jobs/2/note").first().contains("Parts ordered"))
    }

    @Test fun logWorkPostsMinutes() {
        launch()
        compose.onNodeWithTag("queue-log-work").performClick()
        compose.onNodeWithTag("queue-dialog-text").performTextInput("Cleaned movement")
        compose.onNodeWithTag("queue-dialog-minutes").performTextInput("25")
        compose.onNodeWithTag("queue-dialog-confirm").performClick()
        compose.waitUntil(10_000) { sent("POST /v1/work-logs").isNotEmpty() }
        Assert.assertTrue(sent("POST /v1/work-logs").first().contains("25"))
    }

    @Test fun claimPostsToTheJob() {
        launch()
        compose.onNodeWithTag("queue-claim").performClick()
        compose.waitUntil(10_000) { sent("POST /v1/repair-jobs/2/claim").isNotEmpty() }
    }

    @Test fun noUpdateSavesCheckedInNoteAndClearsTheCard() {
        val vm = launch()
        compose.onNodeWithTag("queue-no-update").performClick()
        compose.onNodeWithTag("queue-dialog-confirm").performClick()
        compose.waitUntil(10_000) { vm.state.value.checkedIn == 1 }
        Assert.assertEquals("3", vm.state.value.current?.id)
    }

    @Test fun priorityFilterNarrowsTheQueue() {
        val vm = launch()
        compose.onNodeWithTag("queue-filter").performClick()
        compose.onNodeWithTag("queue-filter-priority-urgent").performClick()
        compose.waitUntil(10_000) { vm.state.value.queue.map { it.id } == listOf("2") }
    }

    @Test fun resetDayDeletesSavedProgress() {
        launch()
        compose.onNodeWithTag("queue-reset-day").performClick()
        compose.onNodeWithTag("queue-reset-confirm").performClick()
        compose.waitUntil(10_000) { sent("DELETE /v1/me/repair-queue-day").isNotEmpty() }
    }
}
