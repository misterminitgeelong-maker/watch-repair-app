package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.CustomFieldsCard
import au.mainspring.nativeapp.ui.screens.AcceptBookingScreen
import okhttp3.mockwebserver.*
import org.junit.*

class CustomFieldsAndAcceptBookingTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val json = "Content-Type" to "application/json"
    private val booking = """{"id":"b1","status":"pending","customer_name":"Sam","requesting_tenant_id":"s","target_operator_tenant_id":"op",
        "requesting_shop_name":"Shop One","target_operator_name":"Op","job_address":"1 A St"}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val p = request.path.orEmpty()
                val body = when {
                    request.method == "GET" && p == "/v1/repair-jobs/j1" -> """{"id":"j1","custom_fields_json":"{\"Serial\":\"X1\"}"}"""
                    request.method == "PATCH" && p == "/v1/repair-jobs/j1/custom-fields" -> """{"ok":true,"fields":{}}"""
                    request.method == "GET" && p.startsWith("/v1/shop-mobile-bookings") -> """{"total":1,"items":[$booking]}"""
                    request.method == "POST" && p == "/v1/shop-mobile-bookings/b1/accept" -> booking.replace("pending", "accepted").replace("\"id\":\"b1\"", "\"id\":\"b1\",\"resulting_auto_key_job_id\":\"job9\"")
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader(json.first, json.second).setBody(body)
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("op", "owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun customFieldsLoadEditAndSaveWholeSet() {
        compose.setContent { MainspringTheme { CustomFieldsCard(CustomFieldJobKind.Watch, "j1") } }
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Custom fields · 1").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithText("Custom fields · 1").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Serial").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithText("Field name").performTextInput("Colour")
        compose.onNodeWithText("Value").performTextInput("Blue")
        compose.onNodeWithText("Add").performClick()
        compose.onNodeWithText("Save fields").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Custom fields saved").fetchSemanticsNodes().isNotEmpty() }
        var patch: RecordedRequest? = null
        while(server.requestCount > 0) { val r = server.takeRequest(1, java.util.concurrent.TimeUnit.SECONDS) ?: break; if(r.method == "PATCH") { patch = r; break } }
        Assert.assertEquals("""{"fields":{"Serial":"X1","Colour":"Blue"}}""", patch!!.body.readUtf8())
    }

    @Test fun acceptsBookingOnExplicitTapAndOffersJob() {
        var opened: String? = null
        compose.setContent { MainspringTheme { AcceptBookingScreen("b1", onBack = {}, onOpenJob = { opened = it }) } }
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Sam").fetchSemanticsNodes().isNotEmpty() }
        Assert.assertTrue(server.requestCount >= 1 && server.takeRequest().method == "GET") // opening the link alone does not accept
        compose.onNodeWithText("Accept and quote").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Open job").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithText("Open job").performClick()
        Assert.assertEquals("job9", opened)
    }
}
