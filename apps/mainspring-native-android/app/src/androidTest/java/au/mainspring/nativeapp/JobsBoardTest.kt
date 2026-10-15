package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.screens.buildBoardColumns
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Board "Move to" status changes (watch and shoe) and the shoe SMS log / resend. */
class JobsBoardTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<String>()
    private var watchStatus = "awaiting_quote"
    private var shoeStatus = "awaiting_quote"

    private fun watch() = """{"id":"w1","watch_id":"x","job_number":"W-1","title":"Service","status":"$watchStatus","priority":"normal","created_at":"2026-10-08T00:00:00Z"}"""
    private fun shoe() = """{"id":"s1","tenant_id":"t","shoe_id":"sh","job_number":"S-1","status_token":"x","title":"Resole","priority":"normal","status":"$shoeStatus","deposit_cents":0,"cost_cents":0,"quote_approval_token":"q","quote_status":"none","created_at":"2026-10-08T00:00:00Z","items":[]}"""
    private val sms = """[{"id":"l1","to_phone":"0412","body":"Hi","event":"job_live","status":"sent","created_at":"2026-10-08T00:00:00Z"}]"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = request.body.readUtf8()
                requests.add("${request.method} $path $body")
                val json = when {
                    path == "/v1/repair-jobs" -> "[${watch()}]"
                    path == "/v1/shoe-repair-jobs" -> "[${shoe()}]"
                    path == "/v1/repair-jobs/w1/status" -> { watchStatus = JsonParser.parseString(body).asJsonObject["status"].asString; watch() }
                    path == "/v1/shoe-repair-jobs/s1/status" -> { shoeStatus = JsonParser.parseString(body).asJsonObject["status"].asString; shoe() }
                    path == "/v1/shoe-repair-jobs/s1/sms-log" -> sms
                    path == "/v1/shoe-repair-jobs/s1/resend-notification" -> sms.trim('[', ']')
                    path == "/v1/shoe-repair-jobs/s1" -> shoe()
                    path.endsWith("/status-history") || path == "/v1/attachments" || path.startsWith("/v1/customers") || path.startsWith("/v1/team") -> "[]"
                    else -> "[]"
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(json)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("board", "tech"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun watchBoardMoveSendsStatusAndUpdatesJob() {
        val m = JobsViewModel(); compose.waitUntil(10_000) { m.state.value.jobs.isNotEmpty() }
        m.moveJob("w1", "working_on")
        compose.waitUntil(10_000) { m.state.value.movingId == null && m.state.value.jobs.single().status == "working_on" }
        val post = requests.single { it.startsWith("POST /v1/repair-jobs/w1/status") }
        Assert.assertEquals("working_on", JsonParser.parseString(post.substringAfter("status ")).asJsonObject["status"].asString)
        val cards = buildBoardColumns(m.state.value.jobs.map { BoardCardForTest.of(it.id, it.status) }, WATCH_PICKER_STATUSES, ::watchStatusLabel)
        Assert.assertEquals(1, cards.single { it.status == "working_on" }.cards.size)
        Assert.assertEquals(0, cards.single { it.status == "awaiting_quote" }.cards.size)
    }

    @Test fun shoeBoardMoveSendsStatusAndUpdatesJob() {
        val m = ShoeJobsViewModel(); compose.waitUntil(10_000) { m.state.value.jobs.isNotEmpty() }
        m.moveJob("s1", "go_ahead")
        compose.waitUntil(10_000) { m.state.value.movingId == null && m.state.value.jobs.single().status == "go_ahead" }
        Assert.assertTrue(requests.any { it.startsWith("POST /v1/shoe-repair-jobs/s1/status") && it.contains("go_ahead") })
    }

    @Test fun shoeSmsLogLoadsAndResendPostsEvent() {
        val m = ShoeJobDetailViewModel("s1", server.url("/").toString())
        compose.waitUntil(10_000) { !m.state.value.loading && m.state.value.smsLog.size == 1 }
        m.resendNotification("job_live")
        compose.waitUntil(10_000) { !m.state.value.resendBusy && m.state.value.resendInfo != null }
        val post = requests.single { it.startsWith("POST /v1/shoe-repair-jobs/s1/resend-notification") }
        Assert.assertEquals("job_live", JsonParser.parseString(post.substringAfter("notification ")).asJsonObject["event"].asString)
    }
}

private object BoardCardForTest {
    fun of(id: String, status: String) = au.mainspring.nativeapp.ui.screens.BoardCard(id, id, "", status)
}
