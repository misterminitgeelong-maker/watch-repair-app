package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class LeadsBoardTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    private val statuses = ConcurrentLinkedQueue<String>()
    private val patches = ConcurrentLinkedQueue<String>()
    private fun lead(id: String, status: String) =
        """{"id":"$id","name":"Lead $id","status":"$status","source":"website_lead","created_at":"2026-10-01T00:00:00Z","suburb_name":"Geelong"}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = when {
                    path == "/v1/prospects/leads" && request.method == "GET" -> {
                        val status = request.requestUrl!!.queryParameter("status"); statuses.add(status ?: "all")
                        when(status) { null -> "[${lead("a", "new")},${lead("b", "contacted")}]"; "contacted" -> "[${lead("b", "contacted")}]"; else -> "[${lead("a", "new")}]" }
                    }
                    path == "/v1/prospects/leads/a" && request.method == "PATCH" -> { patches.add(request.body.readUtf8()); lead("a", "quote_needed") }
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("leads", "owner"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun listLoadsStageFilterRequestsStatusAndUpdateSendsStatus() {
        val model = LeadsViewModel(); compose.waitUntil(10_000) { !model.state.value.loading && model.state.value.all.isNotEmpty() }
        Assert.assertEquals(2, model.state.value.all.size); Assert.assertEquals(2, model.state.value.shown.size)
        Assert.assertEquals(1, model.state.value.counts["new"])
        model.selectStage("contacted"); compose.waitUntil(10_000) { !model.state.value.loading && model.state.value.shown.size == 1 && model.state.value.shown.single().id == "b" }
        Assert.assertTrue(statuses.contains("contacted"))
        model.setStatus(model.state.value.all.first { it.id == "a" }, "quote_needed")
        compose.waitUntil(10_000) { patches.isNotEmpty() }
        val sent = com.google.gson.JsonParser.parseString(patches.peek()).asJsonObject
        Assert.assertEquals("quote_needed", sent["status"].asString)
    }
}
