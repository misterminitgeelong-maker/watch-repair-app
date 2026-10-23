package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class StockWorkflowTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    private val offsets = ConcurrentLinkedQueue<Int>()
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = when(path) {
                    "/v1/stock/items" -> {
                        val offset = request.requestUrl!!.queryParameter("offset")!!.toInt(); offsets.add(offset)
                        val search = request.requestUrl!!.queryParameter("search")
                        val suffix = if(search == null) offset.toString() else search
                        """{"items":[{"id":"item-$suffix","item_code":"BAT-$suffix","group_code":"BAT","system_stock_qty":10,"pack_qty":1,"cost_price_cents":100,"retail_price_cents":200}],"total":2,"limit":1,"offset":$offset}"""
                    }
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("stock", "clerk"); TokenStore.setSessionRole("clerk")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun inventoryPagingAndFilteredSearchResetOffsets() {
        val model = StockViewModel(); compose.waitUntil(10_000) { !model.state.value.loading }
        model.more(); compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals(listOf(0, 1), offsets.toList()); Assert.assertEquals(2, model.state.value.items.size)
        model.search("battery"); compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals(0, offsets.last()); Assert.assertEquals("item-battery", model.state.value.items.single().id)
    }
}
