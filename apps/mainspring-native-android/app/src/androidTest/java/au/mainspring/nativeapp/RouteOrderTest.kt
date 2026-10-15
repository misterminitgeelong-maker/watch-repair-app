package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.AutoKeyJobRead
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class RouteOrderTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    private val patches = ConcurrentLinkedQueue<Triple<String, String, String?>>()
    @Volatile private var optimiseBody = """{"visit_order":[0,2,1],"source":"directions"}"""
    @Volatile private var optimiseCode = 200
    @Volatile private var failPatchFor = ""

    private fun job(id: String, visit: Int? = null) = AutoKeyJobRead(id = id, updatedAt = "2026-10-15T00:00:0${id.last()}Z", tenantId = "t", customerId = "c", jobNumber = id,
        statusToken = "s", title = id, keyQuantity = 1, programmingStatus = "p", priority = "normal", status = "booking_confirmed", depositCents = 0, costCents = 0,
        createdAt = "2026-10-15T00:00:00Z", commissionLeadSource = "other", visitOrder = visit)
    private val jobJson = """{"id":"x","tenant_id":"t","customer_id":"c","job_number":"x","status_token":"s","title":"x","key_quantity":1,"programming_status":"p",
        "priority":"normal","status":"booking_confirmed","deposit_cents":0,"cost_cents":0,"created_at":"2026-10-15T00:00:00Z","commission_lead_source":"other"}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val json = MockResponse().setHeader("Content-Type", "application/json")
                val path = request.path.orEmpty()
                return when {
                    path == "/v1/maps/optimize-driving-route" -> if(optimiseCode == 200) json.setBody(optimiseBody) else json.setResponseCode(optimiseCode).setBody("""{"detail":"not configured"}""")
                    request.method == "PATCH" && path.startsWith("/v1/auto-key-jobs/") -> {
                        val id = path.substringAfterLast('/')
                        patches.add(Triple(id, request.body.readUtf8(), request.getHeader("X-Expected-Updated-At")))
                        if(id == failPatchFor) json.setResponseCode(500).setBody("""{"detail":"boom"}""") else json.setBody(jobJson)
                    }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("route", "owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun idle(m: RouteOrderViewModel) = compose.waitUntil(10_000) { !m.state.value.busy && (m.state.value.message != null || m.state.value.error != null) }
    private val stops get() = listOf(job("j1"), job("j2"), job("j3")).mapIndexed { i, j -> LocatedStop(j, -33.0 - i, 151.0) }

    @Test fun optimisedOrderIsPersistedWithStaleWriteHeader() {
        val m = RouteOrderViewModel(); m.optimise(stops); idle(m)
        val rows = patches.toList().associate { it.first to it }
        Assert.assertEquals(3, rows.size)
        // order [0,2,1] -> j1 first, j3 second, j2 third
        Assert.assertEquals(1, JsonParser.parseString(rows.getValue("j1").second).asJsonObject["visit_order"].asInt)
        Assert.assertEquals(2, JsonParser.parseString(rows.getValue("j3").second).asJsonObject["visit_order"].asInt)
        Assert.assertEquals(3, JsonParser.parseString(rows.getValue("j2").second).asJsonObject["visit_order"].asInt)
        Assert.assertEquals("2026-10-15T00:00:02Z", rows.getValue("j2").third)
        Assert.assertEquals(3, m.state.value.changed)
    }
    @Test fun tooFewStopsDoesNotCallServer() {
        val m = RouteOrderViewModel(); m.optimise(stops.take(1)); Assert.assertNotNull(m.state.value.error); Assert.assertTrue(patches.isEmpty())
    }
    @Test fun unconfiguredOptimiserWritesNothing() {
        optimiseCode = 503
        val m = RouteOrderViewModel(); m.optimise(stops); idle(m)
        Assert.assertNotNull(m.state.value.error); Assert.assertTrue(patches.isEmpty())
    }
    @Test fun malformedOrderIsRejected() {
        optimiseBody = """{"visit_order":[0,0,1],"source":"directions"}"""
        val m = RouteOrderViewModel(); m.optimise(stops); idle(m)
        Assert.assertTrue(patches.isEmpty()); Assert.assertTrue(m.state.value.error!!.contains("unexpected"))
    }
    @Test fun partialFailureReportsHowManySaved() {
        failPatchFor = "j3"
        val m = RouteOrderViewModel(); m.optimise(stops); idle(m)
        Assert.assertTrue(m.state.value.error!!.contains("Saved 1 of 3"))
        Assert.assertEquals(2, patches.size)
    }
    @Test fun clearSendsExplicitNullOnlyForOrderedJobs() {
        val m = RouteOrderViewModel(); m.clear(listOf(job("j1", 1), job("j2"), job("j3", 2))); idle(m)
        Assert.assertEquals(setOf("j1", "j3"), patches.map { it.first }.toSet())
        patches.forEach { Assert.assertTrue(JsonParser.parseString(it.second).asJsonObject["visit_order"].isJsonNull) }
    }
}
