package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.PendingBookingsBanner
import okhttp3.mockwebserver.*
import org.junit.*

class PendingBookingsTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    @Volatile private var code = 200
    private fun row(id: String, status: String, target: String) = """{"id":"$id","status":"$status","customer_name":"C","requesting_tenant_id":"shop","target_operator_tenant_id":"$target",
        "requesting_shop_name":"Shop","target_operator_name":"Op","job_address":"1 A St"}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse =
                if(request.path?.startsWith("/v1/shop-mobile-bookings") == true) {
                    if(code != 200) MockResponse().setResponseCode(code).setBody("""{"detail":"no"}""").setHeader("Content-Type", "application/json")
                    else MockResponse().setHeader("Content-Type", "application/json").setBody(
                        """{"total":4,"items":[${listOf(row("1", "pending", "op"), row("2", "pending", "op"), row("3", "accepted", "op"), row("4", "pending", "other")).joinToString(",")}]}""")
                } else MockResponse().setResponseCode(404)
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("op", "owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun countsOnlyPendingRequestsAddressedToThisOperatorAndOpens() {
        val vm = PendingBookingsViewModel(); var opened = 0
        compose.setContent { MainspringTheme { PendingBookingsBanner({ opened++ }, model = vm) } }
        compose.waitUntil(10_000) { vm.pending.value == 2 }
        compose.onNodeWithText("2 booking requests waiting").performClick()
        Assert.assertEquals(1, opened)
    }
    @Test fun failureShowsNothing() {
        code = 403
        val vm = PendingBookingsViewModel()
        compose.setContent { MainspringTheme { PendingBookingsBanner({}, model = vm) } }
        compose.waitUntil(10_000) { server.requestCount >= 1 }
        compose.onNodeWithText("booking request", substring = true).assertDoesNotExist()
    }
}
