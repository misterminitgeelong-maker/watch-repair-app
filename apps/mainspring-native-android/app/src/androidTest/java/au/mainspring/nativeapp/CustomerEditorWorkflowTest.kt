package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.CustomerEditorScreen
import com.google.gson.*
import okhttp3.mockwebserver.*
import org.junit.*

class CustomerEditorWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var name = "Avery"
    private var phone: String? = "0400000000"
    private var patches = 0
    private var creates = 0
    private var patch = ""
    private var unknownCreate = false
    private var unknownEdit = false
    private var searchLimit = 0
    private fun customer() = JsonObject().apply {
        addProperty("id", "customer-1"); addProperty("tenant_id", "tenant-1"); addProperty("full_name", name)
        addProperty("phone", phone); addProperty("email", "avery@example.test"); addProperty("address", "10 Test Street"); addProperty("notes", "Existing notes"); addProperty("created_at", "2026-10-08T00:00:00Z")
    }.toString()
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val body = when(request.path.orEmpty().substringBefore('?')) {
                    "/v1/customers/customer-1" -> if(request.method == "PATCH") {
                        patches++; patch = request.body.readUtf8()
                        val json = JsonParser.parseString(patch).asJsonObject
                        if(json.has("phone")) phone = json["phone"].takeUnless { it.isJsonNull }?.asString
                        if(json.has("full_name")) name = json["full_name"].asString
                        if(unknownEdit) return MockResponse().setResponseCode(503).setBody("Unknown result")
                        customer()
                    } else customer()
                    "/v1/customers" -> if(request.method == "POST") {
                        creates++
                        if(unknownCreate) return MockResponse().setResponseCode(503).setBody("Unknown creation")
                        customer()
                    } else {
                        searchLimit = request.requestUrl!!.queryParameter("limit")!!.toInt()
                        if(searchLimit > 200) return MockResponse().setResponseCode(422).setBody("Invalid limit")
                        "[${customer()}]"
                    }
                    else -> "[]"
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("customers", "clerk"); TokenStore.setSessionRole("clerk")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun model() = CustomerEditorViewModel("customer-1").also { compose.waitUntil(10_000) { !it.state.value.loading } }
    @Test fun changedOnlyPatchClearsPhoneExplicitlyWithoutOverwritingOtherFields() {
        val model = model(); model.save("Avery", "avery@example.test", "", "10 Test Street", "Existing notes")
        compose.waitUntil(10_000) { !model.state.value.saving }
        Assert.assertTrue(model.state.value.saved)
        val json = JsonParser.parseString(patch).asJsonObject
        Assert.assertEquals(setOf("phone"), json.keySet()); Assert.assertTrue(json["phone"].isJsonNull)
        model.save("Avery", "avery@example.test", "", "10 Test Street", "Existing notes"); compose.waitUntil(10_000) { !model.state.value.saving }
        Assert.assertEquals(1, patches)
    }
    @Test fun peerEditBlocksStalePatchAndSurvivesRecreation() {
        val model = model(); name = "Avery Updated"
        model.save("Avery", "avery@example.test", "0411111111", "10 Test Street", "Existing notes")
        compose.waitUntil(10_000) { !model.state.value.saving }
        Assert.assertTrue(model.state.value.conflict); Assert.assertEquals(0, patches)
        val restored = model(); Assert.assertTrue(restored.state.value.conflict)
        restored.load(discard = true); compose.waitUntil(10_000) { !restored.state.value.loading }
        Assert.assertFalse(restored.state.value.conflict); Assert.assertEquals("Avery Updated", restored.state.value.customer!!.fullName)
    }
    @Test fun discardControlReplacesDraftWithCurrentServerValues() {
        val model = model()
        compose.setContent { MainspringTheme { CustomerEditorScreen("customer-1", {}, vm = model) } }
        compose.onNodeWithText("Name *").performTextReplacement("Draft edit")
        name = "Avery Updated"
        compose.onNodeWithText("Discard edits and load latest customer").performScrollTo().performClick()
        compose.waitUntil(10_000) { !model.state.value.loading }
        compose.onNodeWithText("Avery Updated").assertExists(); compose.onNodeWithText("Draft edit").assertDoesNotExist()
        Assert.assertEquals(0, patches)
    }
    @Test fun acknowledgedCreationRetainsIdAndRequiresStartAnotherAfterRecreation() {
        val model = CustomerEditorViewModel(""); model.save("Avery", "", "", "", "")
        compose.waitUntil(10_000) { !model.state.value.saving }
        val restored = CustomerEditorViewModel(""); Assert.assertTrue(restored.state.value.saved)
        restored.save("Avery", "", "", "", ""); Assert.assertEquals(1, creates)
        Assert.assertEquals("customer-1", restored.state.value.customer!!.id)
        restored.startAnother(); Assert.assertFalse(restored.state.value.saved); Assert.assertNull(restored.state.value.customer)
    }
    @Test fun unknownCreationUsesAllowedSearchLimitAndExistingRecordRecovery() {
        unknownCreate = true
        val model = CustomerEditorViewModel(""); model.save("Avery", "", "", "", "")
        compose.waitUntil(10_000) { !model.state.value.saving }; Assert.assertTrue(model.state.value.unknown)
        val restored = CustomerEditorViewModel(""); restored.reviewRecords("Avery"); compose.waitUntil(10_000) { !restored.state.value.loading }
        Assert.assertEquals(200, searchLimit); Assert.assertTrue(restored.state.value.reviewed)
        restored.useExisting("customer-1"); restored.save("Avery", "", "", "", "")
        Assert.assertFalse(restored.state.value.unknown); Assert.assertTrue(restored.state.value.saved); Assert.assertEquals(1, creates)
    }
    @Test fun lostEditResponseDoesNotReplayPatchOverAcknowledgedServerChange() {
        unknownEdit = true
        val model = model(); model.save("Avery", "avery@example.test", "0411111111", "10 Test Street", "Existing notes")
        compose.waitUntil(10_000) { !model.state.value.saving }
        model.save("Avery", "avery@example.test", "0411111111", "10 Test Street", "Existing notes")
        compose.waitUntil(10_000) { !model.state.value.saving }
        Assert.assertEquals(1, patches); Assert.assertTrue(model.state.value.conflict)
        model.load(discard = true); compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals("0411111111", model.state.value.customer!!.phone)
    }
    @Test fun counterSaleCustomerRecoveryAlsoUsesAllowedCustomerSearchLimit() {
        val request = CounterSaleRequest("", "Avery", "", "", null, "quote", emptyList(), false, false, "Test quote")
        val retained = mapOf("request" to Gson().toJson(request), "uncertain" to "savedCustomerId")
        TokenStore.bindDrafts().saveMessageDraft("counter-sale", Gson().toJson(retained))
        val model = CounterSaleViewModel(); compose.waitUntil(10_000) { !model.state.value.customerLoading }
        model.review(); compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertTrue(model.state.value.reviewed); Assert.assertEquals(200, searchLimit)
        Assert.assertEquals("customer-1", model.state.value.recovery.single().id)
    }
}
