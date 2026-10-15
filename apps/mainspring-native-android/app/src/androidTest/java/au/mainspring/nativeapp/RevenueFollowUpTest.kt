package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class RevenueFollowUpTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    private val queries = ConcurrentLinkedQueue<String>()
    private val puts = ConcurrentLinkedQueue<String>()
    private val putPaths = ConcurrentLinkedQueue<String>()
    @Volatile private var putCode = 200
    private val list = """{"items":[{"key":"unpaid:inv-1","kind":"unpaid","job_id":"j1","job_number":"MS-1","title":"Spare key","customer_name":"Sam","owner_user_id":null,"owner_name":null,"amount_cents":12000,"currency":"AUD","deposit_cents":0,"age_days":3,"due_at":"2026-10-01T00:00:00Z","due":true,"priority":"high","next_action":"Chase payment","note":"","last_contact_at":null,"version":4}],"total":1,"limit":50,"offset":0,"buckets":[],"owners":[{"id":"u1","name":"Ana"}],"generated_at":"2026-10-14T00:00:00Z","timezone":"Australia/Sydney","warnings":[]}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                if(request.method == "PUT" && path.endsWith("/follow-up")) {
                    putPaths.add(path); puts.add(request.body.readUtf8())
                    return if(putCode == 200) MockResponse().setHeader("Content-Type", "application/json").setBody(list.substringAfter("\"items\":[").substringBefore("],\"total\""))
                    else MockResponse().setResponseCode(putCode).setHeader("Content-Type", "application/json").setBody("""{"detail":"This item changed. Refresh and try again."}""")
                }
                if(path == "/v1/revenue-control") { queries.add(request.requestUrl!!.query.orEmpty()); return MockResponse().setHeader("Content-Type", "application/json").setBody(list) }
                return MockResponse().setResponseCode(404)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("revenue", "owner"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun savesFollowUpWithVersionOwnerAndNote() {
        val model = RevenueControlViewModel(); compose.waitUntil(10_000) { model.state.value.items.isNotEmpty() }
        Assert.assertEquals("u1", model.state.value.owners.single().id)
        model.edit(model.state.value.items.single())
        model.saveFollowUp("u1", "3", "Rang, will pay Friday", true)
        compose.waitUntil(10_000) { puts.isNotEmpty() && model.state.value.editing == null && !model.state.value.saving }
        val body = JsonParser.parseString(puts.first()).asJsonObject
        Assert.assertEquals(4, body.get("expected_version").asInt); Assert.assertEquals("u1", body.get("owner_user_id").asString)
        Assert.assertEquals("Rang, will pay Friday", body.get("note").asString); Assert.assertTrue(body.get("contacted").asBoolean)
        Assert.assertFalse(body.get("next_follow_up_at").isJsonNull)
        Assert.assertEquals("/v1/revenue-control/unpaid:inv-1/follow-up", putPaths.first().replace("%3A", ":"))
        compose.waitUntil(10_000) { queries.size >= 2 }
    }

    @Test fun sendsExplicitNullsForUnassignedDueNowAndShowsServerConflict() {
        val model = RevenueControlViewModel(); compose.waitUntil(10_000) { model.state.value.items.isNotEmpty() }
        putCode = 409
        model.edit(model.state.value.items.single()); model.saveFollowUp(null, "now", "", false)
        compose.waitUntil(10_000) { model.state.value.saveError != null }
        val body = JsonParser.parseString(puts.first()).asJsonObject
        Assert.assertTrue(body.get("owner_user_id").isJsonNull); Assert.assertTrue(body.get("next_follow_up_at").isJsonNull)
        Assert.assertNotNull(model.state.value.editing)
        Assert.assertTrue(model.state.value.saveError!!.contains("changed"))
    }

    @Test fun ownerFilterAndSearchAreSentToTheApi() {
        val model = RevenueControlViewModel(); compose.waitUntil(10_000) { queries.isNotEmpty() && !model.state.value.loading }
        model.owner("unassigned"); compose.waitUntil(10_000) { queries.size >= 2 && !model.state.value.loading }
        Assert.assertTrue(queries.last().contains("owner=unassigned"))
        model.search("Sam"); compose.waitUntil(10_000) { queries.size >= 3 && !model.state.value.loading }
        Assert.assertTrue(queries.last().contains("search=Sam") && queries.last().contains("owner=unassigned"))
    }
}
