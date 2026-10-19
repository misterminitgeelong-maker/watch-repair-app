package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.CustomerRead
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.MergeDuplicatesSheet
import au.mainspring.nativeapp.ui.screens.QuotesScreen
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Quotes "+ New Quote" job picker and Customers "Merge duplicates" flow against a MockWebServer. */
class QuoteJobPickerAndMergeFlowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val paths = ConcurrentLinkedQueue<String>()
    private val bodies = ConcurrentLinkedQueue<String>()
    @Volatile private var jobsMode = "ok"
    @Volatile private var mergeFails = false
    private fun job(id: String, number: String, title: String, customer: String, status: String = "awaiting_quote") =
        """{"id":"$id","tenant_id":"t","watch_id":"w","job_number":"$number","title":"$title","status":"$status","priority":"normal","customer_name":"$customer","created_at":"2026-10-01T00:00:00Z"}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                paths.add(request.path.orEmpty())
                val path = request.path.orEmpty().substringBefore('?')
                val body = when(path) {
                    "/v1/quotes" -> "[]"
                    "/v1/repair-jobs" -> when {
                        jobsMode == "error" -> return MockResponse().setResponseCode(500)
                        jobsMode == "empty" -> "[]"
                        request.requestUrl!!.queryParameter("q") == "bob" -> "[${job("j2", "W101", "Strap swap", "Bob Jones")}]"
                        else -> "[${job("j1", "W100", "Omega service", "Avery Smith")},${job("j2", "W101", "Strap swap", "Bob Jones")}]"
                    }
                    "/v1/customers/merge" -> {
                        bodies.add(request.body.readUtf8())
                        return MockResponse().setResponseCode(if(mergeFails) 500 else 204)
                    }
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setBody(body).setHeader("Content-Type", "application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("picker", "owner"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun showQuotes(onNew: (String) -> Unit) = compose.setContent { MainspringTheme { QuotesScreen(onOpenQuote = {}, onNewQuote = onNew) } }

    @Test fun newQuoteSearchesJobsAndOpensTheComposerForThePickedJob() {
        var picked = ""
        showQuotes { picked = it }
        compose.onNodeWithTag("new-quote").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("quote-job-j2").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("quote-job-j1").assertExists()
        compose.onNodeWithTag("quote-job-search").performTextInput("bob")
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("quote-job-j1").fetchSemanticsNodes().isEmpty() }
        Assert.assertTrue(paths.any { it.contains("q=bob") })
        compose.onNodeWithTag("quote-job-j2").performClick()
        Assert.assertEquals("j2", picked)
        compose.onNodeWithTag("quote-job-picker").assertDoesNotExist()
    }

    @Test fun newQuotePickerShowsEmptyAndErrorStates() {
        jobsMode = "empty"
        showQuotes {}
        compose.onNodeWithTag("new-quote").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("No open jobs to quote.").fetchSemanticsNodes().isNotEmpty() }
    }

    @Test fun newQuotePickerShowsServerError() {
        jobsMode = "error"
        showQuotes {}
        compose.onNodeWithTag("new-quote").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Retry").fetchSemanticsNodes().isNotEmpty() }
    }

    private val avery = CustomerRead("c1", "t", "Avery Smith", "avery@example.com", "0412 345 678", null, null, "2026-10-01T00:00:00Z")
    private val averyDup = CustomerRead("c2", "t", "Avery Smyth", null, "0412345678", null, null, "2026-10-02T00:00:00Z")
    private val bob = CustomerRead("c3", "t", "Bob Jones", "bob@example.com", null, null, null, "2026-10-03T00:00:00Z")
    private fun showMerge(onMerged: () -> Unit = {}) = compose.setContent { MainspringTheme { MergeDuplicatesSheet(listOf(avery, averyDup, bob), {}, onMerged) } }

    @Test fun mergePicksKeepThenDuplicateConfirmsAndSendsBothIds() {
        var merged = false
        showMerge { merged = true }
        compose.onNodeWithTag("merge-pick-c1").performClick()
        compose.onNodeWithTag("merge-pick-c1").assertDoesNotExist()
        compose.onNodeWithTag("merge-search").performTextInput("smyth")
        compose.onNodeWithTag("merge-pick-c2").performClick()
        compose.onNodeWithTag("merge-keep-card").assertTextContains("Avery Smith", substring = true)
        compose.onNodeWithTag("merge-duplicate-card").assertTextContains("Avery Smyth", substring = true)
        compose.onNodeWithTag("merge-duplicate-card").assertTextContains("0412345678", substring = true)
        compose.onNodeWithTag("merge-confirm").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("merge-success").fetchSemanticsNodes().isNotEmpty() }
        val body = bodies.single()
        Assert.assertTrue(body, body.contains("\"primary_customer_id\":\"c1\"")); Assert.assertTrue(body, body.contains("\"duplicate_customer_id\":\"c2\""))
        Assert.assertTrue(merged)
    }

    @Test fun mergeFailureShowsErrorAndAllowsRetry() {
        mergeFails = true
        showMerge()
        compose.onNodeWithTag("merge-pick-c1").performClick()
        compose.onNodeWithTag("merge-pick-c2").performClick()
        compose.onNodeWithTag("merge-confirm").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Try again").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("merge-success").assertDoesNotExist()
        mergeFails = false
        compose.onNodeWithTag("merge-confirm").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("merge-success").fetchSemanticsNodes().isNotEmpty() }
    }
}
