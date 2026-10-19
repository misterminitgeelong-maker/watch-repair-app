package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.MobileEditorScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*

class MobileAccountWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var account: String? = null
    private var accountUnavailable = false
    private var writes = 0
    private var patch = ""
    private var expectedVersion: String? = null
    private fun job() = """{"id":"job-1","customer_id":"customer-1","title":"Fleet key replacement","status":"booked","key_quantity":1,"programming_status":"pending","updated_at":"2026-10-08T00:00:00Z","customer_account_id":${account?.let { "\"$it\"" } ?: "null"}}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val body = when(request.path) {
                    "/v1/auto-key-jobs/job-1" -> {
                        if(request.method == "PATCH") {
                            writes++; patch = request.body.readUtf8(); expectedVersion = request.getHeader("X-Expected-Updated-At")
                            val json = JsonParser.parseString(patch).asJsonObject
                            if(json.has("customer_account_id")) account = json["customer_account_id"].takeUnless { it.isJsonNull }?.asString
                        }
                        job()
                    }
                    "/v1/customer-accounts" -> {
                        if(accountUnavailable) return MockResponse().setResponseCode(403).setBody("""{"detail":"Feature disabled"}""")
                        """[{"id":"account-1","name":"Avery Fleet","is_active":true,"customer_ids":["customer-1"]},{"id":"other","name":"Other customer","is_active":true,"customer_ids":["customer-2"]},{"id":"inactive","name":"Old Fleet","is_active":false,"customer_ids":["customer-1"]}]"""
                    }
                    "/v1/users" -> "[]"
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("account-edit", "tech"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun model() = MobileEditorViewModel("job-1").also { compose.waitUntil(10_000) { !it.state.value.loading } }
    @Test fun linkedAccountPickerPersistsSelectionAndSendsVersionedPatch() {
        val model = model()
        compose.setContent { MainspringTheme { MobileEditorScreen("job-1", {}, model) } }
        compose.onNodeWithText("Change billing account").performScrollTo().performClick()
        compose.onNodeWithText("Other customer").assertDoesNotExist(); compose.onNodeWithText("Old Fleet").assertDoesNotExist()
        compose.onNodeWithText("Avery Fleet").performClick()
        val restored = model(); Assert.assertEquals("account-1", restored.state.value.fields["customer_account_id"])
        restored.save(); compose.waitUntil(10_000) { !restored.state.value.busy }
        Assert.assertTrue(restored.state.value.saved); Assert.assertEquals("2026-10-08T00:00:00Z", expectedVersion)
        Assert.assertEquals(setOf("customer_account_id"), JsonParser.parseString(patch).asJsonObject.keySet())
        Assert.assertEquals("account-1", account)
    }
    @Test fun accountRemovalUsesExplicitNullAndUnlinkedOrInactiveAccountsCannotBeAssigned() {
        account = "account-1"
        val model = model()
        model.set("customer_account_id", "other"); model.save(); Assert.assertEquals(0, writes)
        model.set("customer_account_id", "inactive"); model.save(); Assert.assertEquals(0, writes)
        model.set("customer_account_id", ""); model.save(); compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertEquals(1, writes); Assert.assertTrue(JsonParser.parseString(patch).asJsonObject["customer_account_id"].isJsonNull)
    }
    @Test fun unavailableAccountFeaturePreservesExistingBillingAndDoesNotBlockOtherEdits() {
        accountUnavailable = true; account = "account-1"
        val model = model(); model.set("title", "Updated fleet job"); model.save(); compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertTrue(model.state.value.saved); Assert.assertEquals("account-1", account)
        Assert.assertEquals(setOf("title"), JsonParser.parseString(patch).asJsonObject.keySet())
    }
}
