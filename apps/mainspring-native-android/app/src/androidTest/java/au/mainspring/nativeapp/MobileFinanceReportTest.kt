package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class MobileFinanceReportTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    private val queries = ConcurrentLinkedQueue<String>()
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = when(path) {
                    "/v1/reports/auto-key/cockpit" -> """{"attention":[{"key":"late","label":"Late","count":2,"items":[{"id":"j1","job_number":"MS-1","title":"Lockout","scheduled_at":"2026-10-14T01:00:00Z","assigned_name":null}]}],"metrics":[{"key":"collected","label":"Collected","unit":"cents","current":5000,"previous":4000,"partial":true}],"outstanding":{"current":9000,"count":3,"overdue_cents":4000,"aging_cents":{"current":5000,"d8_30":3000,"d31_plus":1000},"aging_counts":{"current":1,"d8_30":1,"d31_plus":1}},"capacity":{"technicians":2,"capacity_minutes":960,"booked_minutes":300,"available_minutes":660,"conflicts":0,"unassigned_today":1},"follow_ups":{},"weekly_target_cents":null}"""
                    "/v1/reports/auto-key/finance" -> {
                        queries.add(request.requestUrl!!.query.orEmpty())
                        """{"period":{"label":"Week","start":"2026-10-12","end":"2026-10-18","complete":false},"metrics":[{"key":"collected","label":"Collected","unit":"cents","current":7000,"previous":null}],"target":null,"conversion":[],"ar_ageing":{"total_cents":9000,"overdue_cents":4000,"buckets":[{"key":"current","label":"Current","cents":5000,"count":1}]},"technicians":[],"data_quality":[]}"""
                    }
                    "/v1/reports/auto-key/finance/export" -> {
                        queries.add("export:" + request.requestUrl!!.query.orEmpty())
                        return MockResponse().setHeader("Content-Type", "text/csv").setBody("a,b\n1,2\n")
                    }
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("mobile-finance", "owner"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun loadsCockpitThenFinanceAndExports() {
        val model = MobileFinanceReportViewModel(); compose.waitUntil(10_000) { model.state.value.cockpit != null }
        val cockpit = model.state.value.cockpit!!
        Assert.assertEquals(2, cockpit.attention.single().count); Assert.assertEquals(1000L, cockpit.outstanding.agingCents.d31Plus)
        Assert.assertNull(cockpit.weeklyTargetCents)
        model.mode("finance"); compose.waitUntil(10_000) { model.state.value.finance != null }
        Assert.assertTrue(queries.first().contains("period=week")); Assert.assertEquals(9000L, model.state.value.finance!!.arAgeing.totalCents)
        model.period("last_month"); compose.waitUntil(10_000) { queries.size >= 2 }
        Assert.assertTrue(queries.last().contains("period=last_month"))
        val bytes = kotlinx.coroutines.runBlocking { model.exportCsv("last_month", "invoices") }
        Assert.assertEquals("a,b\n1,2\n", String(bytes)); Assert.assertTrue(queries.last().contains("kind=invoices"))
    }
    @Test fun clerkIsBlocked() {
        TokenStore.setSessionRole("clerk")
        val model = MobileFinanceReportViewModel()
        Assert.assertEquals("Reports require an owner or manager account.", model.state.value.error)
    }
}
