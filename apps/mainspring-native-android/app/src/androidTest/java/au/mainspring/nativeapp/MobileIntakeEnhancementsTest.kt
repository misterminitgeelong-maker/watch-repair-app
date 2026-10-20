package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.*
import androidx.lifecycle.SavedStateHandle
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.MobileIntakeScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*

/** Server quote suggestions, key-spec lookup, last-vehicle suggestion, address suggestions and the new intake fields. */
class MobileIntakeEnhancementsTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var suggestionPaths = mutableListOf<String>()
    private var createBody = ""
    private var failSuggestions = false
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = when {
                    path == "/v1/auto-key-jobs/quote-suggestions" -> {
                        suggestionPaths += request.path.orEmpty()
                        if(failSuggestions) return MockResponse().setResponseCode(503)
                        """{"pricing_tier":"retail","total_cents":20790,"subtotal_cents":18900,"tax_cents":1890,"line_items":[{"id":"0","description":"Vehicle lockout service","quantity":1,"unit_price_cents":18900,"total_price_cents":18900}]}"""
                    }
                    path == "/v1/vehicle-key-specs/search" -> """{"matches":[{"score":90,"label":"Toyota Hilux 2015-2020","vehicle_make":"Toyota","vehicle_model":"Hilux","year_from":2015,"year_to":2020,"years_label":"2015-2020","key_type":"Flip","chip_type":"4D","tech_notes":"OBD programmable","key_blanks":[{"primary_code":"TOY48"}],"suggested_blade_code":"TOY48"}]}"""
                    path == "/v1/auto-key-jobs" && request.method == "GET" -> """[{"id":"old","tenant_id":"t","customer_id":"customer-1","job_number":"M001","status_token":"x","title":"Old","vehicle_make":"Mazda","vehicle_model":"3","vehicle_year":2018,"registration_plate":"XYZ789","key_quantity":1,"programming_status":"not_required","priority":"normal","status":"completed","deposit_cents":0,"cost_cents":0,"created_at":"2026-01-01","commission_lead_source":"shop"}]"""
                    path == "/v1/auto-key-jobs" -> { createBody = request.body.readUtf8(); """{"id":"job-1"}""" }
                    path == "/v1/watch-catalogue/repairs-config" -> """{"combos":[],"currency":"AUD"}"""
                    else -> "[]"
                }
                return MockResponse().setBody(body).setHeader("Content-Type", "application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("intake-enhance", "tech"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun serverSuggestionIsShownUsingTierQuantityAndExtraPresets() {
        val vm = MobileIntakeViewModel(SavedStateHandle()); vm.set("jobType", "Lockout – Car"); vm.set("quantity", "2"); vm.setExtras(listOf(ExtraService("Diagnostic", "")))
        compose.waitUntil(10_000) { vm.state.value.suggestion?.estimated == false }
        Assert.assertEquals(20790, vm.state.value.suggestion!!.totalCents)
        val last = suggestionPaths.last()
        Assert.assertTrue(last, last.contains("key_quantity=2") && last.contains("pricing_tier=retail") && last.contains("additional_presets=Diagnostic"))
        compose.setContent { MainspringTheme { MobileIntakeScreen({}, {}, vm) } }
        compose.onNodeWithTag("intake-suggested-quote").performScrollTo().assertExists()
    }
    @Test fun unreachableServerFallsBackToAnEstimateAndStillSubmits() {
        failSuggestions = true
        val vm = MobileIntakeViewModel(SavedStateHandle()); vm.set("customerId", "customer-1"); vm.set("jobType", "Duplicate Key"); vm.set("title", "Duplicate")
        compose.waitUntil(10_000) { vm.state.value.suggestion != null }
        Assert.assertTrue(vm.state.value.suggestion!!.estimated)
        vm.submit(); compose.waitUntil(10_000) { vm.field("jobId").isNotBlank() }
        val json = JsonParser.parseString(createBody).asJsonObject
        Assert.assertTrue(json["apply_suggested_quote"].asBoolean); Assert.assertFalse(json.has("cost_cents"))
    }
    @Test fun lastVehicleBannerFillsBlankFieldsOnly() {
        val vm = MobileIntakeViewModel(SavedStateHandle()); vm.set("customerMode", "existing"); vm.set("customerId", "customer-1"); vm.set("plate", "KEEP1")
        compose.waitUntil(10_000) { vm.state.value.lastJob != null }
        compose.setContent { MainspringTheme { MobileIntakeScreen({}, {}, vm) } }
        compose.onNodeWithTag("intake-last-vehicle").performScrollTo().assertExists()
        compose.onNodeWithTag("intake-last-vehicle-use").performClick()
        Assert.assertEquals("Mazda", vm.field("make")); Assert.assertEquals("2018", vm.field("year")); Assert.assertEquals("KEEP1", vm.field("plate"))
        compose.onNodeWithTag("intake-last-vehicle").assertDoesNotExist()
    }
    @Test fun keySpecMatchFillsBladeChipAndNotes() {
        val vm = MobileIntakeViewModel(SavedStateHandle()); vm.set("make", "Toy"); vm.set("model", "Hil")
        compose.waitUntil(10_000) { vm.state.value.specMatches.isNotEmpty() }
        vm.applySpec(vm.state.value.specMatches.first())
        Assert.assertEquals("TOY48", vm.field("blade")); Assert.assertEquals("4D", vm.field("chip")); Assert.assertEquals("Flip", vm.field("keyType")); Assert.assertEquals("2015", vm.field("year"))
    }
    @Test fun addressSuggestionsComeFromTheInjectedSuggesterAndCanBePicked() {
        val vm = MobileIntakeViewModel(SavedStateHandle()); vm.addressSuggester = AddressSuggester { listOf("1 Main St, Sydney NSW 2000") }
        vm.set("address", "1 Main")
        compose.waitUntil(10_000) { vm.state.value.addressSuggestions.isNotEmpty() }
        vm.pickAddress(vm.state.value.addressSuggestions.first())
        Assert.assertEquals("1 Main St, Sydney NSW 2000", vm.field("address")); Assert.assertTrue(vm.state.value.addressSuggestions.isEmpty())
    }
    @Test fun newFieldsAreSentOnCreate() {
        val vm = MobileIntakeViewModel(SavedStateHandle()); vm.set("customerId", "customer-1"); vm.set("title", "Fleet key"); vm.set("blade", "HU66"); vm.set("chip", "ID46")
        vm.set("salesperson", "Sam"); vm.set("commission", "tech_sourced"); vm.setExtras(listOf(ExtraService("Diagnostic", ""), ExtraService("", "Re-shell")))
        compose.waitUntil(10_000) { vm.state.value.suggestion?.estimated == false }
        vm.submit(); compose.waitUntil(10_000) { vm.field("jobId").isNotBlank() }
        val json = JsonParser.parseString(createBody).asJsonObject
        Assert.assertEquals("HU66", json["blade_code"].asString); Assert.assertEquals("ID46", json["chip_type"].asString); Assert.assertEquals("Sam", json["salesperson"].asString)
        Assert.assertEquals("tech_sourced", json["commission_lead_source"].asString); Assert.assertEquals(20790, json["cost_cents"].asInt)
        Assert.assertEquals(2, json["additional_services"].asJsonArray.size())
    }
}
