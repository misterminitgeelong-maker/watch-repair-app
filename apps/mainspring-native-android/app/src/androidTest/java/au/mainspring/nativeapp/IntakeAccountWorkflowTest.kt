package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.*
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.MobileIntakeScreen
import androidx.lifecycle.SavedStateHandle
import androidx.test.platform.app.InstrumentationRegistry
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*

class IntakeAccountWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var mobileBody = ""
    private var creates = 0
    private var rejectJob = false
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val body = when(request.path.orEmpty().substringBefore('?')) {
                    "/v1/customer-accounts" -> """[{"id":"account-1","name":"Avery Fleet","is_active":true,"customer_ids":["customer-1"]}]"""
                    "/v1/auto-key-jobs" -> if(request.method != "POST") "[]" else { creates++; mobileBody = request.body.readUtf8(); if(rejectJob) return MockResponse().setResponseCode(400).setBody("""{"detail":"Plan limit reached"}"""); """{"id":"job-1"}""" }
                    "/v1/customers" -> if(request.method == "POST") """{"id":"saved-customer","full_name":"Avery"}""" else "[]"
                    "/v1/watch-catalogue/repairs-config" -> """{"combos":[],"currency":"AUD"}"""
                    else -> "[]"
                }
                return MockResponse().setBody(body).setHeader("Content-Type","application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("intake-account","tech"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun linkedMobileBillingAccountIsRetainedAndSentToJobCreation() {
        val model = MobileIntakeViewModel(SavedStateHandle()); compose.waitUntil(10_000) { model.state.value.accounts.isNotEmpty() }
        model.set("customerId","customer-1"); model.set("customerMode","existing"); model.set("accountId","account-1"); model.set("title","Fleet key replacement")
        val restored = MobileIntakeViewModel(SavedStateHandle()); compose.waitUntil(10_000) { restored.state.value.accounts.isNotEmpty() }
        restored.submit(); compose.waitUntil(10_000) { !restored.state.value.busy }
        Assert.assertNull(restored.state.value.error); Assert.assertEquals("account-1",JsonParser.parseString(mobileBody).asJsonObject["customer_account_id"].asString)
    }
    @Test fun changingCustomerClearsPriorAccountAndExistingWatchSelection() {
        val mobile = MobileIntakeViewModel(SavedStateHandle()); mobile.set("customerId","customer-1"); mobile.set("accountId","account-1"); mobile.set("customerId","customer-2")
        Assert.assertEquals("",mobile.field("accountId"))
        val shoe = ShoeIntakeViewModel(SavedStateHandle()); shoe.set("customerId","customer-1"); shoe.set("accountId","account-1"); shoe.set("customerMode","new")
        Assert.assertEquals("",shoe.field("accountId"))
        val watch = WatchIntakeViewModel(SavedStateHandle()); watch.setField("customerId","customer-1"); watch.setField("accountId","account-1"); watch.setField("watch.0.id","older-watch"); watch.setField("customerMode","new")
        Assert.assertEquals("",watch.field("accountId")); Assert.assertEquals("",watch.field("watch.0.id"))
    }
    @Test fun unlinkedAccountAndCounterRoleCannotCreateMobileJobs() {
        val model = MobileIntakeViewModel(SavedStateHandle()); compose.waitUntil(10_000) { model.state.value.accounts.isNotEmpty() }
        model.set("customerId","customer-2"); model.set("accountId","account-1"); model.set("title","Replacement key"); model.submit()
        Assert.assertEquals(0,creates); Assert.assertTrue(model.state.value.error.orEmpty().contains("linked active account"))
        model.set("accountId",""); TokenStore.setSessionRole("clerk"); model.submit()
        Assert.assertEquals(0,creates); Assert.assertTrue(model.state.value.error.orEmpty().contains("technician or manager"))
    }
    @Test fun acknowledgedCustomerLocksIntakeIdentityAfterRejectedJobAndRecreation() {
        rejectJob = true
        val model = MobileIntakeViewModel(SavedStateHandle()); model.set("customerMode","new"); model.set("name","Avery"); model.set("title","Replacement key")
        model.submit(); compose.waitUntil(10_000) { !model.state.value.busy }
        val restored = MobileIntakeViewModel(SavedStateHandle())
        Assert.assertEquals("saved-customer",restored.field("customerId")); Assert.assertEquals("true",restored.field("hasAcknowledgement"))
        compose.setContent { MainspringTheme { MobileIntakeScreen({}, {}, restored) } }
        compose.onNode(hasContentDescription("Full Name *")).assertIsNotEnabled()
        compose.onNodeWithText("Discard").assertIsEnabled()
    }
}
