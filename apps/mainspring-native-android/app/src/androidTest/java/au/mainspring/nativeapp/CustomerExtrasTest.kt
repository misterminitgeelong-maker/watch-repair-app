package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class CustomerExtrasTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    // ConcurrentLinkedQueue cannot hold nulls, so every entry is a non-null string.
    private val calls = ConcurrentLinkedQueue<String>()
    private val bodies = ConcurrentLinkedQueue<String>()
    private val customer = """{"id":"c1","tenant_id":"t","full_name":"Avery Customer","email":null,"phone":null,"address":null,"notes":null,"created_at":"2026-10-07T00:00:00Z"}"""
    private val orders = """[{"id":"o1","tenant_id":"t","customer_id":"c1","customer_name":"Avery","title":"Strap","status":"ordered","priority":"urgent","estimated_cost_cents":1500},
        {"id":"o2","tenant_id":"t","customer_id":"other","customer_name":"Other","title":"Crystal","status":"to_order","priority":"normal","estimated_cost_cents":0}]"""
    private val loyalty = """{"loyalty":{"customer_id":"c1","tier_id":1,"tier_name":"silver","tier_label":"Silver","points_balance":120,"points_dollar_value":1.2,"rolling_12m_spend_cents":50000,"joined_at":"2026-01-01T00:00:00Z"},"recent_ledger":[]}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                calls.add(request.method.orEmpty() + " " + request.path.orEmpty())
                val body = when {
                    path == "/v1/customers/c1" -> customer
                    path == "/v1/customers" -> "[$customer]"
                    path == "/v1/customer-orders" && request.method == "GET" -> orders
                    path == "/v1/loyalty/customers/c1" -> loyalty
                    path == "/v1/loyalty/customers/c1/adjust" -> { bodies.add(request.body.readUtf8()); loyalty }
                    path == "/v1/customers/merge" -> { bodies.add(request.body.readUtf8()); return MockResponse().setResponseCode(204) }
                    path == "/v1/customer-orders/o1" && request.method == "DELETE" -> return MockResponse().setResponseCode(204)
                    path == "/v1/customer-orders/o1" && request.method == "PATCH" -> { bodies.add(request.body.readUtf8()); """{"id":"o1","title":"Strap","status":"ordered","priority":"high"}""" }
                    path == "/v1/watches" || path == "/v1/repair-jobs" || path == "/v1/shoe-repair-jobs" || path == "/v1/auto-key-jobs" -> "[]"
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("extras", "owner"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun detail() = CustomerDetailViewModel("c1", setOf("watch")).also { model ->
        compose.waitUntil(10_000) { model.state.value.ordersLoaded && model.state.value.loyalty != null }
    }

    @Test fun detailShowsOnlyThisCustomersOrdersAndLoyalty() {
        val model = detail()
        Assert.assertEquals(listOf("o1"), model.state.value.orders.map { it.id })
        Assert.assertEquals("urgent", model.state.value.orders.single().priority)
        Assert.assertEquals(120, model.state.value.loyalty!!.loyalty.pointsBalance)
    }

    @Test fun adjustSendsPointsAndNote() {
        val model = detail(); model.adjustLoyalty(-20, " Goodwill "); compose.waitUntil(10_000) { bodies.isNotEmpty() && !model.state.value.loyaltySaving }
        val body = bodies.single()
        Assert.assertTrue(body, body.contains("\"points_delta\":-20")); Assert.assertTrue(body, body.contains("\"note\":\"Goodwill\""))
    }

    @Test fun mergeSendsPrimaryAndDuplicate() {
        val model = detail(); model.mergeDuplicate("dup-9"); compose.waitUntil(10_000) { model.state.value.merged || model.state.value.mergeError != null }
        val body = bodies.single()
        Assert.assertTrue(body, body.contains("\"primary_customer_id\":\"c1\"")); Assert.assertTrue(body, body.contains("\"duplicate_customer_id\":\"dup-9\""))
        Assert.assertNull(model.state.value.mergeError)
    }

    @Test fun mergeIntoSelfIsIgnored() {
        val model = detail(); model.mergeDuplicate("c1"); compose.waitForIdle()
        Assert.assertTrue(bodies.isEmpty())
    }

    @Test fun orderEditAndDeleteHitTheApi() {
        val model = CustomerOrdersViewModel(); compose.waitUntil(10_000) { model.state.value.orders.isNotEmpty() }
        val order = model.state.value.orders.first { it.id == "o1" }
        model.edit(order, "Strap", "Acme", 2000, "", "high"); compose.waitUntil(10_000) { bodies.isNotEmpty() && !model.state.value.saving }
        val body = bodies.single()
        Assert.assertTrue(body, body.contains("\"priority\":\"high\"")); Assert.assertTrue(body, body.contains("\"estimated_cost_cents\":2000"))
        model.delete(order); compose.waitUntil(10_000) { calls.any { it.startsWith("DELETE /v1/customer-orders/o1") } && !model.state.value.saving }
    }

    @Test fun customerSortIsSentToTheServer() {
        val model = CustomersViewModel(); compose.waitUntil(10_000) { !model.state.value.loading }
        model.setSort("newest"); compose.waitUntil(10_000) { calls.any { it.contains("sort_by=created_at") && it.contains("sort_dir=desc") } }
    }
}
