package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class RevenueControlTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    private val queries = ConcurrentLinkedQueue<String>()
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = when(path) {
                    "/v1/revenue-control" -> {
                        queries.add(request.requestUrl!!.query.orEmpty())
                        """{"items":[{"key":"unpaid:inv-1","kind":"unpaid","job_id":"j1","job_number":"MS-1","title":"Spare key","customer_name":"Sam","owner_user_id":null,"owner_name":null,"amount_cents":12000,"currency":"AUD","deposit_cents":0,"age_days":3,"due_at":"2026-10-01T00:00:00Z","due":true,"priority":"high","next_action":"Chase payment","note":"","last_contact_at":null,"version":0}],"total":1,"limit":50,"offset":0,"buckets":[{"kind":"unpaid","count":1,"due_count":1,"amount_cents":12000,"unknown_amount_count":0}],"owners":[],"generated_at":"2026-10-14T00:00:00Z","timezone":"Australia/Sydney","warnings":["Amounts are AUD."]}"""
                    }
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("revenue", "clerk"); TokenStore.setSessionRole("clerk")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun loadsDueQueueAndFiltersByCategory() {
        val model = RevenueControlViewModel(); compose.waitUntil(10_000) { !model.state.value.loading && model.state.value.items.isNotEmpty() }
        Assert.assertTrue(queries.first().contains("state=due")); Assert.assertEquals("MS-1", model.state.value.items.single().jobNumber)
        Assert.assertEquals(12000, model.state.value.buckets.single().amountCents)
        model.queue("all"); compose.waitUntil(10_000) { queries.size >= 2 && !model.state.value.loading }
        Assert.assertTrue(queries.last().contains("state=all"))
        model.kind("unpaid"); compose.waitUntil(10_000) { queries.size >= 3 && !model.state.value.loading }
        Assert.assertTrue(queries.last().contains("kind=unpaid"))
    }
}
