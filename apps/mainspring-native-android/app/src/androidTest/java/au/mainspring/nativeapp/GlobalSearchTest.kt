package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.SearchHit
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class GlobalSearchTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<String>()

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val url = request.requestUrl!!
                requests.add(url.encodedPath + "?q=" + url.queryParameter("q"))
                return if (url.encodedPath == "/v1/search") MockResponse().setHeader("Content-Type", "application/json").setBody(
                    """{"hits":[
                    {"kind":"repair_job","id":"w1","title":"Omega Seamaster","subtitle":"W-100","status":"in_progress","href":"/jobs/w1"},
                    {"kind":"shoe_repair_job","id":"s1","title":"Shoe #5","subtitle":"received","status":"received","href":"/shoe-repairs/s1"},
                    {"kind":"auto_key_job","id":"a1","title":"Hilux key","subtitle":"A-1","href":"/auto-key/a1"},
                    {"kind":"customer","id":"c1","title":"Jane Smith","subtitle":"0400 - jane@x.com","href":"/customers/c1"},
                    {"kind":"invoice","id":"i1","title":"Invoice INV-9","subtitle":"paid","status":"paid","href":"/invoices/i1"},
                    {"kind":"quote","id":"q1","title":"Quote","href":"/quotes/q1"}]}""")
                else MockResponse().setResponseCode(404)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun routesMapToShellRoutes() {
        fun r(kind: String) = searchRoute(SearchHit(kind = kind, id = "x"))
        Assert.assertEquals("watchJob/x", r("repair_job")); Assert.assertEquals("shoeJob/x", r("shoe_repair_job"))
        Assert.assertEquals("autoKeyJob/x", r("auto_key_job")); Assert.assertEquals("customer/x", r("customer"))
        Assert.assertEquals("invoice/x", r("invoice")); Assert.assertNull(r("quote"))
    }

    @Test fun shortQueryDoesNotCallApi() {
        val model = SearchViewModel(); model.setQuery("a"); model.setQuery(" b ")
        Thread.sleep(SearchViewModel.DEBOUNCE_MS + 400)
        Assert.assertTrue(requests.isEmpty()); Assert.assertTrue(model.state.value.hits.isEmpty()); Assert.assertFalse(model.state.value.loading)
    }

    @Test fun debouncesToLastQueryAndGroupsResults() {
        val model = SearchViewModel()
        model.setQuery("om"); model.setQuery("ome"); model.setQuery("omega")
        compose.waitUntil(10_000) { model.state.value.searched }
        Assert.assertEquals(listOf("/v1/search?q=omega"), requests.toList())
        val s = model.state.value
        Assert.assertEquals(listOf("w1", "s1", "a1"), s.jobs.map { it.id })
        Assert.assertEquals(listOf("c1"), s.customers.map { it.id })
        Assert.assertEquals(listOf("i1"), s.invoices.map { it.id })
        Assert.assertEquals(5, s.hits.size) // unsupported "quote" kind dropped
    }

    @Test fun clearingQueryResetsResults() {
        val model = SearchViewModel(); model.setQuery("omega"); compose.waitUntil(10_000) { model.state.value.searched }
        model.setQuery(""); Assert.assertTrue(model.state.value.hits.isEmpty())
    }
}
