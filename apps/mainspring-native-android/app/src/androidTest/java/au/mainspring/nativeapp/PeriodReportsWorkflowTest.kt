package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.lifecycle.SavedStateHandle
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.PeriodReportsScreen
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.runBlocking

class PeriodReportsWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val queries = ConcurrentLinkedQueue<String>()
    private var failPrevious = false
    private var delayCurrent = false
    private var largeExport = false
    private val csv = "period,reference_date,revenue_cents\nquarter,2026-10-09,123456\n"
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val url = request.requestUrl!!
                val period = url.queryParameter("period")!!; val date = url.queryParameter("reference_date")!!
                if(url.encodedPath.contains("/export/")) {
                    queries.add("export/$period/$date")
                    return MockResponse().setHeader("Content-Type", "text/csv").setBody(if(largeExport) "x".repeat(2_000_001) else csv)
                }
                queries.add("$period/$date")
                val previous = date == "2026-09-30"
                if(previous && failPrevious) return MockResponse().setResponseCode(503).setBody("Service unavailable")
                val result = MockResponse().setHeader("Content-Type", "application/json").setBody(payload(period, date, previous))
                if(delayCurrent && period == "quarter" && !previous) result.setBodyDelay(700, TimeUnit.MILLISECONDS)
                return result
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("reports", "owner"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun model() = PeriodReportsViewModel(SavedStateHandle(mapOf("period" to "quarter", "date" to "2026-10-09")))
    private fun payload(period: String, date: String, previous: Boolean) = """{"period":"$period","reference_date":"$date","period_start":"${if(previous) "2026-07-01" else "2026-10-01"}","period_end":"${if(previous) "2026-09-30" else "2026-12-31"}","jobs_opened":${if(previous) 10 else 12},"watch_jobs_opened":5,"shoe_jobs_opened":3,"auto_key_jobs_opened":4,"customers_new":7,"financials":{"billed_cents":200000,"revenue_cents":123456,"cost_cents":20000,"gross_profit_cents":103456,"gross_margin_percent":83.8},"sales_funnel":{"quotes_sent":9,"quotes_approved":7,"quotes_declined":2,"approval_rate_percent":77.8},"operations":{"work_minutes":60,"avg_revenue_per_job_cents":10288}}"""

    @Test fun quarterComparisonUsesPreviousServerPeriodAndDisplaysAuthoritativeAmounts() {
        val model = model(); compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals(listOf("quarter/2026-10-09", "quarter/2026-09-30"), queries.toList())
        Assert.assertEquals(10L, model.state.value.previous!!.jobs)
        compose.setContent { MainspringTheme { PeriodReportsScreen({}, model) } }
        compose.onNodeWithTag("period-report-list").performScrollToNode(hasText("Revenue"))
        compose.onNodeWithText("Revenue").assertIsDisplayed()
        compose.onNodeWithTag("report-value-Revenue").assertTextEquals("1234.56")
        saveNativeQaImage(compose.onRoot(), "operational-reports.png")
        compose.onNodeWithTag("period-report-list").performScrollToIndex(0)
        compose.onNodeWithText("Quarter").performScrollTo().assertIsSelected()
        compose.onNodeWithText("Month").performScrollTo().assertIsDisplayed().performClick()
        compose.waitUntil(10_000) { !model.state.value.loading && queries.contains("month/2026-10-09") }
        Assert.assertEquals("month", model.state.value.current!!.period)
    }
    @Test fun failedPreviousPeriodKeepsCurrentReportAndDoesNotInventZeroComparison() {
        failPrevious = true
        val model = model(); compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals(12L, model.state.value.current!!.jobs); Assert.assertNull(model.state.value.previous)
        Assert.assertNull(model.state.value.error); Assert.assertNotNull(model.state.value.comparisonError)
    }
    @Test fun changedPeriodCancelsOlderResponseAndRejectsInvalidDatesWithoutHttp() {
        delayCurrent = true
        val model = model(); compose.waitUntil(10_000) { queries.isNotEmpty() }
        model.select("month", "2026-10-10")
        compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals("month", model.state.value.current!!.period)
        Assert.assertEquals("2026-10-10", model.state.value.current!!.referenceDate)
        val count = server.requestCount
        model.select(date = "2026-02-30")
        Assert.assertEquals(count, server.requestCount); Assert.assertTrue(model.state.value.error!!.contains("valid report date"))
    }
    @Test fun technicianCannotLoadManagerReports() {
        TokenStore.setSessionRole("tech")
        val model = model()
        Assert.assertEquals(0, server.requestCount); Assert.assertFalse(model.state.value.loading)
        Assert.assertTrue(model.state.value.error!!.contains("owner or manager"))
    }
    @Test fun csvExportUsesSelectedPeriodAndWritesExactServerBytes() = runBlocking {
        val model = model(); compose.waitUntil(10_000) { !model.state.value.loading }
        val bytes = model.exportCsv("quarter", "2026-10-09")
        Assert.assertTrue(queries.contains("export/quarter/2026-10-09")); Assert.assertEquals(csv, bytes.toString(Charsets.UTF_8))
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = java.io.File(context.cacheDir, "report-export-test.csv")
        try {
            saveReportExport(context, android.net.Uri.fromFile(file), bytes)
            Assert.assertArrayEquals(bytes, file.readBytes())
        } finally { file.delete() }
    }
    @Test fun oversizedCsvIsRejectedBeforeItCanBeSaved() = runBlocking {
        largeExport = true
        val model = model(); compose.waitUntil(10_000) { !model.state.value.loading }
        val result = runCatching { model.exportCsv("quarter", "2026-10-09") }
        Assert.assertTrue(result.exceptionOrNull()!!.message!!.contains("file size"))
    }
    @Test fun exportRejectsInvalidSelectionAndRoleBeforeHttp() = runBlocking {
        val model = model(); compose.waitUntil(10_000) { !model.state.value.loading }
        val count = server.requestCount
        Assert.assertTrue(runCatching { model.exportCsv("invalid", "2026-10-09") }.isFailure)
        Assert.assertTrue(runCatching { model.exportCsv("quarter", "2026-02-30") }.isFailure)
        TokenStore.setSessionRole("tech")
        Assert.assertTrue(runCatching { model.exportCsv("quarter", "2026-10-09") }.isFailure)
        Assert.assertEquals(count, server.requestCount)
    }
}
