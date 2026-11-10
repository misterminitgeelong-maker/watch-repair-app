package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.EngravingScreen
import com.google.gson.JsonParser
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Operator event-to-collection journey against the same JSON fields/actions used by FastAPI. */
class EngravingParityWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<Pair<String, String>>()
    private val exportQueries = ConcurrentLinkedQueue<Pair<String?, String?>>()
    @Volatile private var created = false
    @Volatile private var hasOrder = false
    @Volatile private var status = "waiting"
    @Volatile private var medalsDone = 0
    @Volatile private var paid = false
    @Volatile private var rejectEdit = false
    private fun event() = """{"id":"event","name":"Saturday athletics","event_date":"2026-11-14","location":"Geelong","price_cents":1500,"minutes_per_medal":3,"status":"open","sms_enabled":false,"online_payments":false,"online_payments_ready":false,"public_url":"https://mainspring.au/engrave/event-token","stats":{"waiting":${if(hasOrder && status == "waiting") 1 else 0},"engraving":${if(status == "engraving") 1 else 0},"ready":${if(status == "ready") 1 else 0},"collected":${if(status == "collected") 1 else 0},"medals_remaining":${if(hasOrder && medalsDone == 0) 1 else 0},"paid_cents":${if(paid) 1500 else 0},"unpaid_cents":${if(hasOrder && !paid) 1500 else 0}}}"""
    private fun order() = """{"id":"order","event_id":"event","order_number":"E001","status_token":"status-token","athlete_name":"Avery Lee","line2":"100 metres","place":"1st","qty":1,"medals_done":$medalsDone,"phone":null,"status":"$status","paid":$paid,"payment_method":${if(paid) "\"stall\"" else "null"},"amount_cents":1500,"source":"walk_up","notes":null,"ready_sms_status":${if(status == "ready") "\"skipped\"" else "null"}}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        requests.clear(); exportQueries.clear(); created = false; hasOrder = false; status = "waiting"; medalsDone = 0; paid = false; rejectEdit = false
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath
                val body = if(request.method in listOf("POST", "PATCH")) request.body.readUtf8() else ""
                requests += path to body
                val json = MockResponse().setHeader("Content-Type", "application/json")
                return when {
                    path == "/v1/engraving/events" && request.method == "GET" -> json.setBody(if(created) "[${event()}]" else "[]")
                    path == "/v1/engraving/events" -> { created = true; json.setBody(event()) }
                    path == "/v1/engraving/events/event/queue" -> json.setBody("""{"event":${event()},"orders":${if(hasOrder) "[${order()}]" else "[]"}}""")
                    path == "/v1/engraving/events/event/orders" -> { hasOrder = true; paid = JsonParser.parseString(body).asJsonObject["paid"].asBoolean; json.setBody(order()) }
                    path == "/v1/engraving/orders/order/start" -> { status = "engraving"; json.setBody(order()) }
                    path == "/v1/engraving/orders/order/medal-done" -> { medalsDone = 1; status = "ready"; json.setBody(order()) }
                    path == "/v1/engraving/orders/order" && rejectEdit -> json.setResponseCode(422).setBody("""{"detail":"Please check the athlete name"}""")
                    path == "/v1/engraving/orders/order" -> {
                        val fields = JsonParser.parseString(body).asJsonObject
                        fields["status"]?.let { status = it.asString }; fields["paid"]?.let { paid = it.asBoolean }; json.setBody(order())
                    }
                    path == "/v1/engraving/events/event/export" -> { exportQueries += request.requestUrl!!.queryParameter("software") to request.requestUrl!!.queryParameter("limit"); MockResponse().setHeader("Content-Type", "text/csv").setBody("Name,Line2,Place,Order,Medal\r\nAvery Lee,100 metres,1st Place,E001,1\r\n") }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("engraving", "tech"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun awaitText(text: String) = compose.waitUntil(10_000) { compose.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty() }
    private fun newEvent() {
        awaitText("New engraving event")
        compose.waitUntil(10_000) { runCatching { compose.onNodeWithText("New engraving event").assertIsEnabled(); true }.getOrDefault(false) }
        compose.onNodeWithText("New engraving event").performClick()
        compose.onNodeWithText("Event name").performTextInput("Saturday athletics")
        compose.onNodeWithText("Date (DD/MM/YYYY)").performScrollTo().performTextInput("14/11/2026")
        compose.onNodeWithText("Save").performClick()
        awaitText("Walk-up order")
    }
    private fun walkUp() {
        compose.waitUntil(10_000) { runCatching { compose.onNodeWithText("Walk-up order").assertIsEnabled(); true }.getOrDefault(false) }
        compose.onNodeWithText("Walk-up order").performClick()
        compose.onNodeWithText("Athlete’s name").performScrollTo().performTextInput("Avery Lee")
        compose.onNodeWithText("Second line").performScrollTo().performTextInput("100 metres")
        compose.onNode(isToggleable()).performScrollTo().performClick()
        compose.onNodeWithText("Save").performClick()
        compose.waitUntil(10_000) { requests.any { it.first.endsWith("/event/orders") } }
        awaitText("Start E001 · Avery Lee")
    }
    @Test fun eventWalkUpEngravingReadyAndCollectionUseTheServerActions() {
        compose.setContent { MainspringTheme { EngravingScreen({}) } }
        newEvent(); walkUp()
        val eventBody = JsonParser.parseString(requests.first { it.first == "/v1/engraving/events" && it.second.isNotBlank() }.second).asJsonObject
        Assert.assertEquals("2026-11-14", eventBody["event_date"].asString); Assert.assertEquals(1500, eventBody["price_cents"].asInt)
        val orderBody = JsonParser.parseString(requests.first { it.first.endsWith("/event/orders") }.second).asJsonObject
        Assert.assertEquals("Avery Lee", orderBody["athlete_name"].asString); Assert.assertEquals("100 metres", orderBody["line2"].asString)
        compose.onNodeWithText("Start E001 · Avery Lee").performScrollTo().performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("engraving-medal-done").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("engraving-medal-done").performScrollTo()
        saveNativeQaImage(compose.onRoot(), "parity-20261111-engraving-queue.png")
        compose.onNodeWithTag("engraving-medal-done").performScrollTo().performClick()
        compose.waitUntil(10_000) { status == "ready" }
        // Ready orders move to the Ready filter after the final medal.
        compose.onNodeWithTag("engraving-content").performScrollToNode(hasText("Ready", substring = false))
        compose.onNodeWithText("Ready", substring = false).performClick()
        compose.onNodeWithTag("engraving-content").performScrollToNode(hasText("Collected", substring = false))
        compose.onNodeWithText("Collected", substring = false).performClick()
        compose.onNodeWithText("Confirm").performClick()
        compose.waitUntil(10_000) { status == "collected" }
        val collection = requests.last { it.first == "/v1/engraving/orders/order" }.second
        Assert.assertEquals("collected", JsonParser.parseString(collection).asJsonObject["status"].asString)
        Assert.assertTrue(paid)
    }
    @Test fun failedOrderEditKeepsTheFormAndShowsTheServerError() {
        compose.setContent { MainspringTheme { EngravingScreen({}) } }
        newEvent(); walkUp(); rejectEdit = true
        compose.onNodeWithTag("engraving-content").performScrollToNode(hasText("Edit", substring = false))
        compose.onNodeWithText("Edit", substring = false).performClick()
        compose.onNodeWithText("Athlete’s name").performScrollTo().performTextReplacement("Avery Lee corrected")
        compose.onNodeWithText("Save").performClick()
        awaitText("Please check the athlete name")
        compose.onNodeWithText("Edit order").assertExists()
        compose.onNodeWithText("Athlete’s name").assertTextContains("Avery Lee corrected")
    }
    @Test fun laserExportPreservesSoftwareLimitAndReturnedBytes() {
        created = true; hasOrder = true
        val vm = EngravingViewModel()
        compose.setContent { MainspringTheme { EngravingScreen({}, vm) } }
        awaitText("Open queue"); compose.onNodeWithText("Open queue").performClick(); awaitText("Walk-up order")
        val bytes = runBlocking { vm.export("lightburn", 12) }
        Assert.assertTrue(bytes.toString(Charsets.UTF_8).contains("Avery Lee"))
        Assert.assertEquals("lightburn" to "12", exportQueries.single())
        val before = requests.count { it.first.endsWith("/export") }
        try { runBlocking { vm.export("csv", 501) }; Assert.fail("Invalid export limit accepted") } catch(_: IllegalArgumentException) {}
        Assert.assertEquals(before, requests.count { it.first.endsWith("/export") })
    }
}
