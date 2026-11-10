package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.*
import androidx.lifecycle.SavedStateHandle
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class MobileParentParityWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<RecordedRequest>()
    private var showInvite = false
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests.add(request)
                val path = request.requestUrl!!.encodedPath
                val body = when(path) {
                    "/v1/auto-key-jobs/page" -> """{"items":[],"total":0}"""
                    "/v1/users" -> "[]"
                    "/v1/reports/auto-key/cockpit" -> "{}"
                    "/v1/reports/auto-key/cockpit/target" -> """{"weekly_target_cents":250000}"""
                    "/v1/shop-mobile-bookings" -> """{"items":[],"total":0}"""
                    "/v1/shop-mobile-bookings/operators" -> "[]"
                    "/v1/shop-mobile-bookings/coverage-contact" -> """{"hq_contact":"support@example.test"}"""
                    "/v1/shop-mobile-bookings/suggest-operator" -> """{"tenant_id":"operator-1","tenant_name":"Demo Operator","routing_rule":"territory"}"""
                    "/v1/auto-key-jobs/quote-suggestions" -> """{"total_cents":10000,"line_items":[]}"""
                    "/v1/auto-key-jobs" -> if(request.method == "POST") """{"id":"job-created"}""" else "[]"
                    "/v1/customer-accounts" -> "[]"
                    "/v1/parent-accounts/me" -> """{"parent_account_id":"p","parent_account_name":"Demo Network","my_role":"hq_admin","site_count":1,"pending_link_requests":[]}"""
                    "/v1/parent-accounts/me/sites" -> """{"sites":[],"total":0}"""
                    "/v1/parent-accounts/me/activity" -> "[]"
                    "/v1/network-link-requests" -> if(showInvite) """[{"id":"invite-1","parent_account_name":"Inviting Network","tenant_name":"Demo Shop","tenant_slug":"demo-shop","status":"pending","created_at":"2026-11-11T00:00:00Z"}]""" else "[]"
                    "/v1/parent-accounts/me/shop-booking-usage" -> """{"month":"2026-11","booking_tenant_count":0,"shops":[]}"""
                    "/v1/network-link-requests/invite-1/accept" -> { showInvite = false; """{"id":"invite-1","status":"accepted"}""" }
                    else -> "[]"
                }
                return MockResponse().setBody(body).setHeader("Content-Type", "application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("mobile-parity", "owner"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun directorySendsCombinedFiltersToServerAndAllFocusesAreUsable() {
        val vm = AutoKeyJobsViewModel()
        compose.waitUntil(10_000) { !vm.state.value.loading }
        vm.status("quote_sent"); vm.technician("tech-1"); vm.category("pipeline"); vm.focus("quote_follow_up")
        compose.waitUntil(10_000) { requests.any { it.requestUrl?.queryParameter("focus") == "quote_follow_up" } }
        val req = requests.last { it.requestUrl?.queryParameter("focus") == "quote_follow_up" }.requestUrl!!
        Assert.assertEquals("quote_sent", req.queryParameter("status")); Assert.assertEquals("tech-1", req.queryParameter("assigned_user_id")); Assert.assertEquals("pipeline", req.queryParameter("category"))
    }
    @Test fun bookingPreviewUsesSuburbAndStateAndShowsRealOperator() {
        val vm = BookingViewModel(); vm.set("suburb", "Richmond"); vm.set("state_code", "VIC")
        compose.waitUntil(10_000) { vm.state.value.route != null }
        Assert.assertEquals("Demo Operator", vm.state.value.route!!.name)
        val req = requests.last { it.requestUrl?.encodedPath == "/v1/shop-mobile-bookings/suggest-operator" }.requestUrl!!
        Assert.assertEquals("Richmond", req.queryParameter("suburb")); Assert.assertEquals("VIC", req.queryParameter("state_code"))
    }
    @Test fun bookingAutocompleteUsesAvailableDeviceGeocoderAndResolvesRoutingFields() {
        val vm = BookingViewModel()
        vm.addressSuggester = object: AddressSuggester {
            override suspend fun suggest(query: String) = listOf("1 Synthetic Street, Richmond VIC")
            override suspend fun resolvePlace(picked: String) = PlaceDetails(picked, "Richmond", "VIC", "3121", -37.8, 145.0)
        }
        vm.set("job_address", "1 Synthetic")
        compose.waitUntil(10_000) { vm.state.value.suggestions.isNotEmpty() }
        vm.pickAddress(vm.state.value.suggestions.single())
        compose.waitUntil(10_000) { vm.state.value.route != null }
        Assert.assertEquals("Richmond", vm.state.value.fields["suburb"]); Assert.assertEquals("VIC", vm.state.value.fields["state_code"])
        Assert.assertFalse(requests.any { it.requestUrl?.encodedPath?.startsWith("/v1/places/") == true })
    }
    @Test fun ownerSavesCashTargetInCents() {
        val vm = MobileFinanceReportViewModel(); compose.waitUntil(10_000) { !vm.state.value.loading }
        vm.setTarget("2500.00")
        compose.waitUntil(10_000) { requests.any { it.method == "PATCH" && it.requestUrl?.encodedPath?.endsWith("/target") == true } }
        val body = requests.last { it.method == "PATCH" }.body.readUtf8()
        Assert.assertEquals(250000, JsonParser.parseString(body).asJsonObject["weekly_target_cents"].asInt)
    }
    @Test fun catalogueSelectedPriceReachesIntakeAndManualEditClearsReference() {
        val vm = MobileIntakeViewModel(SavedStateHandle())
        vm.set("customerId", "customer"); vm.set("title", "Duplicate key")
        vm.selectPricing(PricingRow("price-1", service = "Duplicate", callout = true), "general_service", "120.00")
        Assert.assertEquals("price-1", vm.field("pricingRef")); vm.submit()
        compose.waitUntil(10_000) { vm.field("jobId") == "job-created" }
        val body = requests.last { it.requestUrl?.encodedPath == "/v1/auto-key-jobs" && it.method == "POST" }.body.readUtf8()
        val json = JsonParser.parseString(body).asJsonObject
        Assert.assertEquals(12000, json["cost_cents"].asInt); Assert.assertEquals("price-1", json["pricing_ref_id"].asString); Assert.assertTrue(json["callout_inclusive"].asBoolean)
        vm.manualPrice("130.00"); Assert.assertEquals("", vm.field("pricingRef")); Assert.assertEquals("130.00", vm.field("manualPrice"))
    }
    @Test fun networkMembershipIsSentOnlyAfterOwnerConfirms() {
        showInvite = true
        compose.setContent { au.mainspring.nativeapp.ui.MainspringTheme { au.mainspring.nativeapp.ui.screens.MyShopsScreen({}, {}) } }
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Accept").fetchSemanticsNodes().isNotEmpty() }
        Assert.assertFalse(requests.any { it.requestUrl?.encodedPath?.endsWith("/accept") == true })
        compose.onNodeWithText("Accept").performClick()
        compose.onNodeWithText("Join Inviting Network?").assertExists()
        Assert.assertFalse(requests.any { it.requestUrl?.encodedPath?.endsWith("/accept") == true })
        compose.onNodeWithText("Confirm").performClick()
        compose.waitUntil(10_000) { requests.any { it.requestUrl?.encodedPath?.endsWith("/accept") == true } }
    }
    @Test fun bookingOnlyHomeOffersBookingsMessagesAndInbox() {
        var route = ""
        compose.setContent { au.mainspring.nativeapp.ui.MainspringTheme { au.mainspring.nativeapp.ui.screens.BookingOnlyHomeScreen({ route = it }, "Demo shop") } }
        compose.onNodeWithTag("booking-home-new").assertExists().performClick()
        Assert.assertEquals("newBookingRequest", route)
        compose.onNodeWithTag("booking-home-networkMessages").performScrollTo().assertExists()
        compose.onNodeWithTag("booking-home-inbox").performScrollTo().assertExists()
        compose.onAllNodesWithText("Invoices").assertCountEquals(0)
        compose.onAllNodesWithText("Inventory").assertCountEquals(0)
    }
}
