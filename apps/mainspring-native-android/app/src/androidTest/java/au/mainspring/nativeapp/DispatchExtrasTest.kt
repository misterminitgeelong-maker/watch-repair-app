package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.DispatchPoolScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.atomic.AtomicInteger

class DispatchExtrasTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val reminderPosts = AtomicInteger()
    private val poolGets = AtomicInteger()
    private val baseBodies = ConcurrentLinkedQueue<String>()
    @Volatile private var reminderCode = 200
    @Volatile private var pool = """[{"id":"p1","customer_name":"Avery","job_address":"1 A St","ring":1,"created_at":"2026-10-07T00:00:00Z"}]"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val json = MockResponse().setHeader("Content-Type", "application/json")
                return when(request.path) {
                    "/v1/pool" -> { poolGets.incrementAndGet(); json.setBody(pool) }
                    "/v1/auto-key-jobs/day-before-reminders" -> { reminderPosts.incrementAndGet()
                        if(reminderCode == 200) json.setBody("""{"sent":3}""") else json.setResponseCode(reminderCode).setBody("""{"detail":"x"}""") }
                    "/v1/settings/dispatch-base-location" -> { baseBodies.add(request.body.readUtf8()); json.setBody("""{"base_lat":-33.8,"base_lng":151.2,"ring_radius_km":15}""") }
                    "/v1/users" -> json.setBody("""[{"id":"u1","full_name":"Tess Tech","role":"tech","is_active":true},{"id":"u2","full_name":"Gone","role":"tech","is_active":false}]""")
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("extras", "owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun idle(m: DispatchExtrasViewModel) = compose.waitUntil(10_000) { !m.state.value.busy }

    @Test fun remindersReportCountAndDoubleTapSendsOnce() {
        val m = DispatchExtrasViewModel(); m.sendReminders(); m.sendReminders(); idle(m)
        compose.waitUntil(10_000) { m.state.value.message != null }
        Assert.assertEquals(1, reminderPosts.get()); Assert.assertTrue(m.state.value.message!!.contains("3 customers"))
    }
    @Test fun unknownReminderOutcomeBlocksRepeatUntilAcknowledged() {
        reminderCode = 503
        val m = DispatchExtrasViewModel(); m.sendReminders(); idle(m)
        compose.waitUntil(10_000) { m.state.value.uncertain }
        m.sendReminders(); Assert.assertEquals(1, reminderPosts.get())
        m.acknowledgeUncertain(); reminderCode = 200; m.sendReminders(); idle(m)
        compose.waitUntil(10_000) { reminderPosts.get() == 2 }
    }
    @Test fun clientErrorAllowsImmediateRetry() {
        reminderCode = 403
        val m = DispatchExtrasViewModel(); m.sendReminders(); idle(m)
        compose.waitUntil(10_000) { m.state.value.error != null }
        Assert.assertFalse(m.state.value.uncertain)
    }
    @Test fun techniciansLoadActiveOnly() {
        val m = DispatchExtrasViewModel()
        compose.waitUntil(10_000) { m.state.value.technicians.isNotEmpty() }
        Assert.assertEquals(listOf("Tess Tech"), m.state.value.technicians.map { it.name })
    }
    @Test fun baseLocationValidatesThenSends() {
        val m = DispatchExtrasViewModel(); m.saveBaseLocation("abc", 10); Assert.assertTrue(baseBodies.isEmpty()); Assert.assertNotNull(m.state.value.error)
        m.saveBaseLocation("1 Test Street, Sydney", 15); idle(m)
        compose.waitUntil(10_000) { m.state.value.baseSaved != null }
        val body = JsonParser.parseString(baseBodies.poll()).asJsonObject
        Assert.assertEquals("1 Test Street, Sydney", body["address"].asString); Assert.assertEquals(15, body["ring_radius_km"].asInt)
    }
    @Test fun poolPollingPicksUpNewJobsAndShowsRingHeading() {
        val vm = DispatchPoolViewModel()
        compose.setContent { MainspringTheme { DispatchPoolScreen({}, {}, {}, vm, DispatchExtrasViewModel(), pollMs = 150) } }
        compose.waitUntil(10_000) { vm.state.value.jobs.size == 1 }
        compose.onNodeWithText("Ring 1 jobs").assertExists()
        pool = """[{"id":"p1","customer_name":"Avery","job_address":"1 A St","ring":1,"created_at":"2026-10-07T00:00:00Z"},
            {"id":"p2","customer_name":"Blake","job_address":"2 B St","ring":2,"created_at":"2026-10-08T00:00:00Z"}]"""
        compose.waitUntil(10_000) { vm.state.value.jobs.size == 2 }
        compose.onNodeWithText("Blake").assertExists(); compose.onNodeWithText("Ring 2 jobs").assertExists()
        Assert.assertTrue(poolGets.get() >= 2)
    }
}
