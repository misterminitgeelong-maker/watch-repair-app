package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.lifecycle.SavedStateHandle
import androidx.test.platform.app.InstrumentationRegistry
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*

class CustomIntakeWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var failCustom = false
    private var shoeBody = ""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val body = when(request.path.orEmpty().substringBefore('?')) {
                    "/v1/watch-catalogue/items" -> """[{"key":"base","name":"Base repair","price_cents":1000,"pricing_type":"fixed"}]"""
                    "/v1/watch-catalogue/repairs-config" -> """{"combos":[],"currency":"AUD"}"""
                    "/v1/shoe-catalogue/items" -> "[]"
                    "/v1/custom-services" -> {
                        if(failCustom) return MockResponse().setResponseCode(503).setBody("Temporarily unavailable")
                        if(request.requestUrl!!.queryParameter("service_type") == "watch") """[{"key":"custom__watch-test","name":"Custom seal test","group_id":"custom","group_label":"Custom","price_cents":1325,"price":13.25,"pricing_type":"fixed"}]"""
                        else """[{"key":"custom__shoe-test","name":"Custom sole work","group_id":"custom","group_label":"Custom","price_cents":1475,"price":14.75,"pricing_type":"fixed"}]"""
                    }
                    "/v1/shoe-repair-jobs/shoes" -> """{"id":"shoe-1"}"""
                    "/v1/shoe-repair-jobs" -> { shoeBody = request.body.readUtf8(); """{"id":"job-1"}""" }
                    else -> "[]"
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("custom-intake", "tech"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun customWatchServicePreservesServerKeyAndExactPreQuotePrice() {
        val model = WatchIntakeViewModel(SavedStateHandle()); compose.waitUntil(10_000) { model.state.value.catalogue.size == 2 }
        model.toggleService("custom__watch-test")
        Assert.assertEquals(setOf("custom__watch-test"), model.selectedServices())
        Assert.assertEquals("Custom seal test", model.field("title")); Assert.assertEquals("13.25", model.field("preQuote"))
        model.toggleService("base"); Assert.assertEquals("23.25", model.field("preQuote"))
    }
    @Test fun customShoeServiceIsSentWithItsRealKeyGroupAndPrice() {
        val model = ShoeIntakeViewModel(SavedStateHandle()); compose.waitUntil(10_000) { model.state.value.catalogue.isNotEmpty() }
        model.set("customerId", "customer-1"); model.toggle(0, "custom__shoe-test")
        model.submit(InstrumentationRegistry.getInstrumentation().targetContext)
        compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertTrue(model.state.value.complete)
        val line = JsonParser.parseString(shoeBody).asJsonObject["items"].asJsonArray.single().asJsonObject
        Assert.assertEquals("custom__shoe-test", line["catalogue_key"].asString)
        Assert.assertEquals("custom", line["catalogue_group"].asString); Assert.assertEquals(1475, line["unit_price_cents"].asInt)
    }
    @Test fun failedCustomCatalogueRetainsRegularCatalogueAndShowsMissingServices() {
        failCustom = true
        val model = WatchIntakeViewModel(SavedStateHandle()); compose.waitUntil(10_000) { model.state.value.error != null }
        Assert.assertEquals("base", model.state.value.catalogue.single().key)
        Assert.assertTrue(model.state.value.error!!.contains("Custom services unavailable"))
    }
}
