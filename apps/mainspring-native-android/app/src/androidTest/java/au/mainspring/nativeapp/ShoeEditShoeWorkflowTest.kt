package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*

/** Compile-checked MockWebServer test: PATCH shoe, then link an existing shoe. Run on a device only when wanted. */
class ShoeEditShoeWorkflowTest {
    private lateinit var server: MockWebServer
    private var patched = ""
    private var linked = ""
    private val job = """{"id":"job-1","tenant_id":"t","shoe_id":"s1","job_number":"12","status_token":"x","title":"Heels","priority":"normal","status":"awaiting_quote",
        "deposit_cents":0,"cost_cents":0,"quote_approval_token":"q","quote_status":"none","created_at":"2026-01-01T00:00:00Z","shoe":{"id":"s1","customer_id":"c1","brand":"Ecco"}}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val body = when("${request.method} ${request.path}") {
                    "PATCH /v1/shoe-repair-jobs/shoes/s1" -> { patched = request.body.readUtf8(); """{"id":"s1","customer_id":"c1","brand":"Clarks"}""" }
                    "POST /v1/shoe-repair-jobs/job-1/shoes" -> { linked = JsonParser.parseString(request.body.readUtf8()).asJsonObject["shoe_id"].asString; job }
                    "GET /v1/shoe-repair-jobs/job-1" -> job
                    "GET /v1/shoe-repair-jobs/shoes?customer_id=c1" -> """[{"id":"s1","customer_id":"c1"},{"id":"s2","customer_id":"c1"}]"""
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setBody(body).setHeader("Content-Type", "application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString())
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun apiPatchesAndLinksShoes() = kotlinx.coroutines.runBlocking {
        val api = au.mainspring.nativeapp.api.ApiClient.api
        api.updateShoe("s1", shoeUpdateBody("", "Clarks", "", ""))
        Assert.assertEquals("Clarks", JsonParser.parseString(patched).asJsonObject["brand"].asString)
        Assert.assertEquals(2, api.listShoes("c1").size)
        api.linkShoe("job-1", au.mainspring.nativeapp.api.ShoeLink("s2")); Assert.assertEquals("s2", linked)
    }
}
