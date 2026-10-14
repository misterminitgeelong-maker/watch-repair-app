package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class CataloguePricesTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<String>()
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests.add(request.path.orEmpty())
                val path = request.path.orEmpty().substringBefore('?')
                val q = request.requestUrl!!.queryParameter("q") ?: "all"
                val body = when(path) {
                    "/v1/watch-catalogue/groups" -> """[{"id":"batteries","label":"Batteries"}]"""
                    "/v1/watch-catalogue/items" -> """[{"key":"bat-$q","name":"Battery $q","price_cents":2500,"pricing_type":"fixed","group_id":"batteries","group_label":"Batteries"}]"""
                    "/v1/shoe-catalogue/groups" -> """[{"id":"soles","label":"Soles"}]"""
                    "/v1/shoe-catalogue/items" -> """[{"key":"sole-$q","name":"Resole $q","price_cents":8000,"pricing_type":"pair_from","group_id":"soles","group_label":"Soles","estimated_days_min":3,"estimated_days_max":7}]"""
                    "/v1/shoe-catalogue/combos" -> """[{"id":"c1","name":"Two pairs","discount":"10%","rule":"Second pair 10% off"}]"""
                    "/v1/shoe-catalogue/guarantee" -> """{"shoe_repairs":"90 day guarantee"}"""
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("catalogue", "clerk"); TokenStore.setSessionRole("clerk")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun watchCatalogueLoadsGroupsAndSearches() {
        val model = CatalogueViewModel(); compose.waitUntil(10_000) { !model.state.value.loading && model.state.value.items.isNotEmpty() }
        Assert.assertEquals("Battery all", model.state.value.items.single().name)
        Assert.assertEquals("Batteries", model.state.value.groups.single().label)
        model.search("seiko"); compose.waitUntil(10_000) { !model.state.value.loading && model.state.value.items.single().key == "bat-seiko" }
        Assert.assertTrue(requests.any { it.startsWith("/v1/watch-catalogue/items") && it.contains("q=seiko") })
        Assert.assertEquals(1, requests.count { it.startsWith("/v1/watch-catalogue/groups") })
    }
    @Test fun shoeServicesLoadItemsCombosAndGuarantee() {
        val model = ShoeServicesViewModel(); compose.waitUntil(10_000) { !model.state.value.loading && model.state.value.items.isNotEmpty() }
        val state = model.state.value
        Assert.assertEquals("pair_from", state.items.single().pricingType)
        Assert.assertEquals("Two pairs", state.combos.single().name); Assert.assertEquals("90 day guarantee", state.guarantee)
        model.group("soles"); compose.waitUntil(10_000) { !model.state.value.loading && requests.any { it.contains("group=soles") } }
        Assert.assertNull(model.state.value.error)
    }
}
