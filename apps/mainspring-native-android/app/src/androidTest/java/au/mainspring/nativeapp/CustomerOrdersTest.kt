package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class CustomerOrdersTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val patches = ConcurrentLinkedQueue<String>()
    private val posts = ConcurrentLinkedQueue<String>()
    private val queries = ConcurrentLinkedQueue<String>()
    private val row = """{"id":"o1","tenant_id":"t","customer_id":null,"customer_name":"Sam","title":"Strap","description":null,"supplier":"Acme","status":"%s","priority":"normal","estimated_cost_cents":1500,"notes":null}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = when {
                    path == "/v1/customer-orders" && request.method == "GET" -> { queries.add(request.requestUrl!!.queryParameter("status").orEmpty()); "[" + row.format("to_order") + "]" }
                    path == "/v1/customer-orders" && request.method == "POST" -> { posts.add(request.body.readUtf8()); row.format("to_order") }
                    path == "/v1/customer-orders/o1" && request.method == "PATCH" -> { patches.add(request.body.readUtf8()); row.format("ordered") }
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("orders", "clerk"); TokenStore.setSessionRole("clerk")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun filterAndStatusChangeHitTheApi() {
        val model = CustomerOrdersViewModel(); try { compose.waitUntil(10_000) { !model.state.value.loading && model.state.value.orders.isNotEmpty() } } catch(e: Throwable) { throw AssertionError("state=${model.state.value}", e) }
        Assert.assertEquals("Strap", model.state.value.orders.single().title)
        model.filter("ordered"); compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals("ordered", queries.last())
        model.setStatus(model.state.value.orders.single(), "ordered"); compose.waitUntil(10_000) { patches.isNotEmpty() && !model.state.value.saving }
        Assert.assertTrue(patches.single().contains("\"status\":\"ordered\""))
    }
    @Test fun createSendsPriorityAndCustomerId() {
        val model = CustomerOrdersViewModel(); compose.waitUntil(10_000) { !model.state.value.loading }
        model.create("Strap", "Acme", 1500, "", "urgent", "c-42"); compose.waitUntil(10_000) { posts.isNotEmpty() && !model.state.value.saving }
        val body = posts.single()
        Assert.assertTrue(body, body.contains("\"priority\":\"urgent\""))
        Assert.assertTrue(body, body.contains("\"customer_id\":\"c-42\""))
    }
}
