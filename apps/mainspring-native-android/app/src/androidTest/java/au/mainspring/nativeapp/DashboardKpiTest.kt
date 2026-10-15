package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import okhttp3.mockwebserver.*
import org.junit.*

class DashboardKpiTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val body = when(request.path.orEmpty().substringBefore('?')) {
                    "/v1/reports/summary" -> """{"counts":{"jobs":3,"customers":2,"watches":2,"quotes":1,"invoices":1},"sales_funnel":{"approved_quotes":1,"sent_quotes":2,"declined_quotes":0,"approval_rate_percent":50.0},"financials":{"billed_cents":150000,"revenue_cents":123456,"cost_cents":50000,"outstanding_cents":26544,"gross_profit_cents":73456,"gross_margin_percent":59.5},"operations":{"work_minutes":60,"avg_revenue_per_job_cents":41152,"quote_to_invoice_pct":50.0}}"""
                    "/v1/reports/widgets" -> """{"overdue_jobs_count":2,"quotes_pending_7d_count":1,"overdue_invoices_count":3,"overdue_collection_count":4}"""
                    "/v1/inbox/count" -> """{"count":5}"""
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun dashboardLoadsKpisActionCountsAndInboxCount() {
        val model = DashboardViewModel(); compose.waitUntil(10_000) { !model.state.value.loading }
        val s = model.state.value
        Assert.assertEquals(123456, s.summary?.financials?.revenueCents)
        Assert.assertEquals(26544, s.summary?.financials?.outstandingCents)
        Assert.assertEquals(2, s.widgets?.overdueJobsCount)
        Assert.assertEquals(4, s.widgets?.overdueCollectionCount)
        Assert.assertEquals(5, s.inboxCount)
        Assert.assertTrue(TokenStore.canManageInvoices())
    }
}
