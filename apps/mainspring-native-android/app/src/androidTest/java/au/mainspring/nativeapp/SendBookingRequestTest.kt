package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class SendBookingRequestTest {
    private lateinit var server: MockWebServer
    private val bodies = ConcurrentLinkedQueue<String>()
    private var failWith = 0
    private val job = """{"id":"job-1","tenant_id":"t","customer_id":"c","job_number":"AK-1","status_token":"s","title":"Sam - Job","key_quantity":1,
        "programming_status":"pending","priority":"normal","status":"awaiting_customer_details","deposit_cents":0,"cost_cents":0,"created_at":"2026-01-01T00:00:00Z",
        "commission_lead_source":"other","customer_name":"Sam","customer_phone":"0412345678"}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.path != "/v1/auto-key-jobs/quick-intake") return MockResponse().setResponseCode(404)
                bodies.add(request.body.readUtf8())
                if (failWith != 0) return MockResponse().setResponseCode(failWith).setBody("""{"detail":"nope"}""").setHeader("Content-Type", "application/json")
                return MockResponse().setResponseCode(201).setBody(job).setHeader("Content-Type", "application/json")
            }
        }; server.start()
        TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("tenant", "operator")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun wait(m: SendBookingRequestViewModel) { val end = System.currentTimeMillis() + 10_000; while (m.state.value.busy && System.currentTimeMillis() < end) Thread.sleep(20) }

    @Test fun blankPhoneIsRejectedWithoutRequest() {
        val m = SendBookingRequestViewModel(); m.phone("  "); m.send()
        Assert.assertTrue(bodies.isEmpty()); Assert.assertNotNull(m.state.value.error)
    }
    @Test fun sendsTrimmedPhoneAndDefaultsName() {
        val m = SendBookingRequestViewModel(); m.phone(" 0412345678 "); m.send(); wait(m)
        val body = JsonParser.parseString(bodies.poll()).asJsonObject
        Assert.assertEquals("0412345678", body["phone"].asString); Assert.assertEquals("Customer", body["full_name"].asString)
        Assert.assertEquals("AK-1", m.state.value.result?.jobNumber)
    }
    @Test fun doubleTapSendsOnce() {
        val m = SendBookingRequestViewModel(); m.phone("0412345678"); m.name("Sam"); m.send(); m.send(); wait(m)
        Thread.sleep(200); Assert.assertEquals(1, bodies.size)
        m.send(); Assert.assertEquals(1, bodies.size)
    }
    @Test fun serverErrorBlocksRepeatUntilChecked() {
        failWith = 503
        val m = SendBookingRequestViewModel(); m.phone("0412345678"); m.send(); wait(m)
        Assert.assertTrue(m.state.value.uncertain)
        val restored = SendBookingRequestViewModel(); Assert.assertTrue(restored.state.value.uncertain)
        restored.send(); Assert.assertEquals(1, bodies.size)
        restored.checkedWithCustomer(); Assert.assertFalse(restored.state.value.uncertain)
        Assert.assertEquals("0412345678", restored.state.value.phone)
    }
    @Test fun clientErrorAllowsRetry() {
        failWith = 400
        val m = SendBookingRequestViewModel(); m.phone("0412345678"); m.send(); wait(m)
        Assert.assertFalse(m.state.value.uncertain); Assert.assertNull(m.state.value.result)
    }
}
