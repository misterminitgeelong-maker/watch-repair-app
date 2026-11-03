package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.BusinessAccountEditorScreen
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*

class BusinessAccountEditorTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var writes = 0
    private var failCreate = false
    private var patchBody = ""
    private var createBody = ""
    private var current = JsonParser.parseString("""{"id":"account-1","name":"Avery Fleet","contact_email":"fleet@example.test","payment_terms_days":30,"is_active":true,"customer_ids":[]}""").asJsonObject
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                when {
                    request.method == "POST" -> {
                        writes++; createBody = request.body.readUtf8()
                        if(failCreate) return MockResponse().setResponseCode(503)
                        current = JsonParser.parseString(createBody).asJsonObject.apply { addProperty("id","account-1"); addProperty("is_active",true); add("customer_ids",com.google.gson.JsonArray()) }
                    }
                    request.method == "PATCH" -> { patchBody = request.body.readUtf8(); JsonParser.parseString(patchBody).asJsonObject.entrySet().forEach { current.add(it.key,it.value) } }
                    path == "/v1/customer-accounts" -> return MockResponse().setBody(if(writes > 0 && !failCreate) "[$current]" else "[]").setHeader("Content-Type","application/json")
                }
                return MockResponse().setBody(current.toString()).setHeader("Content-Type","application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("accounts","manager"); TokenStore.setSessionRole("manager")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun createUsesNativeConfirmationAndPersistsAcknowledgedId() {
        val model = BusinessAccountEditorViewModel("")
        compose.setContent { MainspringTheme { BusinessAccountEditorScreen("", {}, {}, model) } }
        compose.onNodeWithText("Account name *").performTextInput("Avery Fleet")
        compose.onNodeWithText("Fleet size").performScrollTo().performTextInput("15")
        compose.onNodeWithText("Corporate Fleet").performScrollTo().performSemanticsAction(androidx.compose.ui.semantics.SemanticsActions.OnClick) { it() }
        compose.onNodeWithText("Create account").performScrollTo().performClick(); Assert.assertEquals(0,writes)
        compose.onNodeWithText("Confirm account save").performClick()
        compose.waitUntil(10_000) { model.state.value.createdId != null }
        val body = JsonParser.parseString(createBody).asJsonObject
        Assert.assertEquals(15,body["fleet_size"].asInt); Assert.assertEquals("Corporate Fleet",body["account_type"].asString)
        val restored = BusinessAccountEditorViewModel(""); restored.save()
        Assert.assertEquals("account-1",restored.state.value.createdId); Assert.assertEquals(1,writes)
    }
    @Test fun unknownCreatePersistsDraftAndRequiresFreshDirectoryReview() {
        failCreate = true
        val model = BusinessAccountEditorViewModel(""); model.set("name","Avery Fleet"); model.save()
        compose.waitUntil(10_000) { !model.state.value.busy }
        val restored = BusinessAccountEditorViewModel("")
        Assert.assertTrue(restored.state.value.uncertain); restored.save(); Assert.assertEquals(1,writes)
        compose.waitUntil(10_000) { restored.state.value.historyChecked }
        Assert.assertEquals("Avery Fleet",restored.state.value.fields["name"])
        restored.checkedAccounts(); Assert.assertFalse(restored.state.value.uncertain)
    }
    @Test fun nullableContactClearPatchesOnlyChangedField() {
        val model = BusinessAccountEditorViewModel("account-1"); compose.waitUntil(10_000) { !model.state.value.loading }
        model.set("contact_email",""); model.save(); compose.waitUntil(10_000) { model.state.value.saved }
        val body = JsonParser.parseString(patchBody).asJsonObject
        Assert.assertTrue(body["contact_email"].isJsonNull); Assert.assertEquals(1,body.size())
    }
    @Test fun freshAccountComparisonRejectsStaleDraftWithoutPatch() {
        val model = BusinessAccountEditorViewModel("account-1"); compose.waitUntil(10_000) { !model.state.value.loading }
        model.set("notes","Earlier operator's notes"); current.addProperty("name","Changed by another operator")
        model.save(); compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertTrue(model.state.value.conflict); Assert.assertEquals("",patchBody)
        Assert.assertEquals("Earlier operator's notes",model.state.value.fields["notes"])
    }
}
