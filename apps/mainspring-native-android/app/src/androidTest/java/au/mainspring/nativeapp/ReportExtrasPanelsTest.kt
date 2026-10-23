package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.ReportExtrasScreen
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Sales and activity (ReportExtrasScreen): category panels, status breakdown panels and the audit log render from the server. */
class ReportExtrasPanelsTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val paths = ConcurrentLinkedQueue<String>()
    @Volatile private var role = "owner"

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath; paths.add(path)
                val json = MockResponse().setHeader("Content-Type", "application/json")
                return when(path) {
                    "/v1/reports/category-summary" -> json.setBody("""{"watch":{"jobs":4,"billed_cents":50000,"revenue_cents":40000,"cost_cents":10000,"outstanding_cents":10000},"shoe":{"jobs":2,"billed_cents":8000,"revenue_cents":8000,"cost_cents":0,"outstanding_cents":0},"mobile":{"jobs":3,"billed_cents":30000,"revenue_cents":25000,"cost_cents":5000,"outstanding_cents":5000}}""")
                    "/v1/reports/gst-summary" -> json.setBody("{}")
                    "/v1/reports/tech-breakdown" -> json.setBody("""[{"user_id":"u1","user_name":"Tess Tech","total_minutes":120,"jobs_count":3}]""")
                    "/v1/reports/trends" -> json.setBody("""{"months":[{"month":"2026-09","jobs_opened":5,"revenue_cents":12000}]}""")
                    "/v1/reports/activity" -> json.setBody("""[{"id":"e1","actor_email":"boss@shop.test","entity_type":"job","event_type":"status","event_summary":"Marked job M001 complete","created_at":"2026-10-19T01:00:00Z"}]""")
                    "/v1/reports/summary" -> json.setBody("""{"counts":{"jobs":9,"customers":5,"watches":4,"quotes":6,"invoices":3,"shoe_jobs":2},"jobs_by_status":{"awaiting_quote":4,"collected":2},"shoe_jobs_by_status":{"in_progress":2},"shoe_quotes":{"by_status":{"sent":1},"approval_rate_percent":50.0},"quotes_by_status":{"sent":3,"approved":2},"sales_funnel":{"approved_quotes":2,"sent_quotes":3,"declined_quotes":1,"approval_rate_percent":66.7},"financials":{"billed_cents":0,"revenue_cents":0,"cost_cents":0,"outstanding_cents":0,"gross_profit_cents":0,"gross_margin_percent":0.0},"operations":{"work_minutes":0,"avg_revenue_per_job_cents":0,"quote_to_invoice_pct":0.0}}""")
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("reports", role); TokenStore.setSessionRole(role)
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun salesCategoriesStatusPanelsAndActivityAreShown() {
        val vm = ReportExtrasViewModel()
        compose.setContent { MainspringTheme { ReportExtrasScreen({}, vm, embedded = true) } }
        compose.waitUntil(10_000) { vm.state.value.summary != null && vm.state.value.statusSummary != null && vm.state.value.activity.isNotEmpty() }
        compose.onNodeWithTag("report-extras").performScrollToNode(hasText("Watch repairs"))
        compose.onNodeWithText("Watch repairs").assertIsDisplayed()
        compose.onNodeWithTag("report-extras").performScrollToNode(hasTestTag("status-jobs"))
        compose.onNodeWithTag("status-jobs").assertIsDisplayed()
        compose.onNodeWithTag("report-extras").performScrollToNode(hasText("Marked job M001 complete"))
        compose.onNodeWithText("Marked job M001 complete").assertIsDisplayed()
        Assert.assertTrue(paths.contains("/v1/reports/category-summary") && paths.contains("/v1/reports/summary") && paths.contains("/v1/reports/activity"))
    }

    @Test fun nonManagersAreToldAndNothingIsRequested() {
        TokenStore.setSessionRole("tech")
        val vm = ReportExtrasViewModel()
        compose.setContent { MainspringTheme { ReportExtrasScreen({}, vm, embedded = true) } }
        compose.onNodeWithText("Owner or manager only").assertIsDisplayed()
        Assert.assertTrue(paths.isEmpty())
    }
}
