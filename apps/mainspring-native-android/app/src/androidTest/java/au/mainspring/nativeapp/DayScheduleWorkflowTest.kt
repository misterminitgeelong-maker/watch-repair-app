package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.AutoKeyJobsScreen
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class DayScheduleWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val dates = ConcurrentLinkedQueue<String>()
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val day = request.requestUrl!!.queryParameter("date_from") ?: "2026-10-09"
                if(request.requestUrl!!.queryParameter("date_from") != null) {
                    dates.add(day)
                    Assert.assertEquals("scheduled",request.requestUrl!!.queryParameter("date_field"))
                    Assert.assertEquals(day,request.requestUrl!!.queryParameter("date_to"))
                }
                return MockResponse().setBody("""{"total":2,"limit":50,"offset":0,"items":[{"id":"late","job_number":"M002","title":"Later appointment","status":"booked","key_quantity":1,"programming_status":"pending","scheduled_at":"${day}T11:00:00+11:00"},{"id":"early","job_number":"M001","title":"Earlier appointment","status":"booked","key_quantity":1,"programming_status":"pending","scheduled_at":"${day}T09:00:00+11:00"}]}""").setHeader("Content-Type","application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("schedule","operator"); TokenStore.setCalendarTimezone("Australia/Sydney")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun scheduled() = AutoKeyJobsViewModel().also { model ->
        model.day("2026-10-09"); compose.waitUntil(10_000) { !model.state.value.loading && model.state.value.jobs.size == 2 }
    }
    @Test fun dayControlsUseShopCivilDateAndSortLoadedBookingsByTime() {
        val model = scheduled()
        Assert.assertEquals(listOf("early","late"),model.state.value.jobs.map { it.id })
        Assert.assertEquals("all",model.state.value.directory)
        compose.setContent { MainspringTheme { AutoKeyJobsScreen({}, {}, {}, model) } }
        compose.onNodeWithText("Next day").performScrollTo().performClick()
        compose.waitUntil(10_000) { !model.state.value.loading && dates.contains("2026-10-10") }
        Assert.assertEquals("2026-10-10",model.state.value.day)
        compose.onNodeWithText("Clear date").performScrollTo().performClick()
        compose.waitUntil(10_000) { !model.state.value.loading }; Assert.assertNull(model.state.value.day)
    }
    @Test fun nativeDatePickerRetainsSelectedDayForNewZealandShop() {
        TokenStore.setCalendarTimezone("Pacific/Auckland")
        val model = scheduled()
        compose.setContent { MainspringTheme { AutoKeyJobsScreen({}, {}, {}, model) } }
        compose.onNodeWithText("Schedule by day").performScrollTo().performClick()
        compose.onNodeWithText("Show appointments").performClick()
        compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals("2026-10-09",model.state.value.day)
        Assert.assertTrue(dates.contains("2026-10-09"))
        saveNativeQaImage(compose.onRoot(), "mobile-day-schedule.png")
    }
    @Test fun invalidScheduleDateDoesNotIssueAnotherRequest() {
        val model = scheduled(); val count = server.requestCount
        model.day("2026-02-30")
        Assert.assertEquals(count,server.requestCount); Assert.assertEquals("2026-10-09",model.state.value.day)
        Assert.assertTrue(model.state.value.error.orEmpty().contains("valid schedule date"))
    }
}
