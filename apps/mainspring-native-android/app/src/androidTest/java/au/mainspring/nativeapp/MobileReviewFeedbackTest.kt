package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.lifecycle.SavedStateHandle
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.*
import au.mainspring.nativeapp.ui.screens.*
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Dropdowns must keep existing request keys, custom titles and unsaved service notes. */
class MobileReviewFeedbackTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<RecordedRequest>()
    @Before fun setup() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        TokenStore.init(context); TokenStore.clear(); TokenStore.setDraftScope("review-feedback", "owner"); TokenStore.setSessionRole("owner")
        DesignPreferences.init(context); DesignPreferences.select(AppAppearance.MAINSPRING)
        server = MockWebServer().apply { dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests.add(request)
                val body = when(request.requestUrl!!.encodedPath) {
                    "/v1/auto-key-jobs/page" -> """{"items":[],"total":0}"""
                    "/v1/users" -> """[{"id":"tech-1","full_name":"Review technician","role":"tech","is_active":true}]"""
                    "/v1/auto-key-jobs/quote-suggestions" -> """{"total_cents":10000,"line_items":[]}"""
                    else -> "[]"
                }
                return MockResponse().setBody(body).setHeader("Content-Type", "application/json")
            }
        }; start() }
        TokenStore.saveApiBaseUrl(server.url("/").toString())
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun filterDropdownsSendCombinedKeysAndResetToAllValues() {
        val vm = AutoKeyJobsViewModel()
        compose.waitUntil(10_000) { vm.state.value.technicians.isNotEmpty() && !vm.state.value.loading }
        compose.setContent { MainspringTheme { AutoKeyJobsScreen({}, {}, {}, viewModel = vm) } }
        compose.onNodeWithTag("filters-button").performClick()
        // Options stay inside their dropdown instead of taking over the filter sheet.
        compose.onAllNodesWithText("Awaiting Customer Details").assertCountEquals(0)
        fun choose(tag: String, key: String) {
            compose.onNodeWithTag(tag).performScrollTo().performClick()
            compose.onNodeWithTag("$tag-$key").performScrollTo().performClick()
        }
        choose("mobile-filter-status", "quote_sent")
        choose("mobile-filter-technician", "tech-1")
        choose("mobile-filter-category", "pipeline")
        choose("mobile-filter-focus", "quote_follow_up")
        compose.waitUntil(10_000) { requests.any { request ->
            val url = request.requestUrl!!
            url.queryParameter("focus") == "quote_follow_up" && url.queryParameter("status") == "quote_sent" &&
                url.queryParameter("assigned_user_id") == "tech-1" && url.queryParameter("category") == "pipeline"
        } }
        Assert.assertEquals("quote_sent", vm.currentView().mobileStatus)
        Assert.assertEquals("tech-1", vm.currentView().technicianId)
        Assert.assertEquals("pipeline", vm.currentView().mobileCategory)
        compose.onNodeWithText("Reset").performScrollTo().performClick()
        compose.waitUntil(5_000) { vm.state.value.focus == null && vm.state.value.statusFilter == null && vm.state.value.technicianFilter == null && vm.state.value.categoryFilter == null }
        compose.onNodeWithTag("mobile-filter-status").assertTextContains("All statuses")
    }

    @Test fun intakeDropdownPreservesCustomTypesTitlesAndAdditionalServiceNotes() {
        val vm = MobileIntakeViewModel(SavedStateHandle())
        vm.set("jobType", "Manual specialty service"); vm.set("title", "Customer-specific job title")
        vm.setExtras(listOf(ExtraService("", "Inspect the existing wiring")))
        compose.setContent { MainspringTheme { MobileIntakeScreen({}, {}, vm) } }
        compose.onNodeWithTag("intake-job-type").assertTextContains("Manual specialty service").performClick()
        // Restored manual service names remain selectable without being normalized to a preset.
        compose.onNodeWithTag("intake-job-type-Manual specialty service").assertExists().performScrollTo().performClick()
        Assert.assertEquals("Manual specialty service", vm.field("jobType"))
        compose.onNodeWithTag("intake-job-type").performClick()
        compose.onNodeWithTag("intake-job-type-All Keys Lost").performScrollTo().performClick()
        Assert.assertEquals("All Keys Lost", vm.field("jobType"))
        Assert.assertEquals("Customer-specific job title", vm.field("title"))
        compose.onNodeWithTag("intake-extra-type-0").performScrollTo().performClick()
        compose.onNodeWithTag("intake-extra-type-0-Diagnostic").performScrollTo().performClick()
        Assert.assertEquals("Diagnostic", vm.extras().single().preset)
        Assert.assertEquals("Inspect the existing wiring", vm.extras().single().custom)
        compose.onNodeWithTag("intake-extra-type-0").performClick()
        compose.onNodeWithTag("intake-extra-type-0-").performScrollTo().performClick()
        Assert.assertEquals("", vm.extras().single().preset)
        Assert.assertEquals("Inspect the existing wiring", vm.extras().single().custom)
    }

    @Test fun selectingAnIntakePresetStillFillsAnUntouchedJobTitle() {
        val vm = MobileIntakeViewModel(SavedStateHandle())
        compose.setContent { MainspringTheme { MobileIntakeScreen({}, {}, vm) } }
        compose.onNodeWithTag("intake-job-type").performClick()
        compose.onNodeWithTag("intake-job-type-Duplicate Key").performScrollTo().performClick()
        Assert.assertEquals("Duplicate Key", vm.field("title"))
        compose.onNodeWithTag("intake-job-type").performClick()
        compose.onNodeWithTag("intake-job-type-Diagnostic").performScrollTo().performClick()
        Assert.assertEquals("Diagnostic", vm.field("title"))
    }
}
