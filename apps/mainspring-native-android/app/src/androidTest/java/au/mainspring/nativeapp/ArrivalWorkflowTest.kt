package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.ArrivalMessageScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*

class ArrivalWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var enabled = true
    private var failSend = false
    private var phone = "+61400000000"
    private var messages = 0
    private var sentWindow = ""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val body = when(request.path.orEmpty()) {
                    "/v1/auto-key-jobs/job-1" -> """{"id":"job-1","customer_id":"customer-1","title":"Replacement key"}"""
                    "/v1/customers/customer-1" -> """{"id":"customer-1","full_name":"Avery","phone":"$phone"}"""
                    "/v1/auth/session" -> """{"tenant_id":"tenant-1","tenant_slug":"test","user":{"id":"user-1","full_name":"Operator","role":"manager"},"mobile_services_customer_sms_enabled":$enabled}"""
                    "/v1/auto-key-jobs/job-1/arrival-sms" -> {
                        messages++; sentWindow = JsonParser.parseString(request.body.readUtf8()).asJsonObject["time_window"].asString
                        if(failSend) return MockResponse().setResponseCode(503)
                        """{"ok":true}"""
                    }
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setBody(body).setHeader("Content-Type","application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("arrival","operator"); TokenStore.setSessionRole("manager")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun vm() = ArrivalMessageViewModel("job-1").also { model -> compose.waitUntil(10_000) { !model.state.value.loading } }
    @Test fun confirmedArrivalRequestRetainsAcceptanceAcrossRecreation() {
        val model = vm()
        compose.setContent { MainspringTheme { ArrivalMessageScreen("job-1", {}, model) } }
        compose.onNodeWithText("Arrival window, e.g. 9–11 am").performTextInput("9–11 am")
        compose.onNodeWithText("Send arrival SMS").performScrollTo().performClick(); Assert.assertEquals(0,messages)
        compose.onNodeWithText("Confirm arrival message").performClick()
        compose.waitUntil(10_000) { model.state.value.draft.accepted && !model.state.value.busy }
        Assert.assertEquals("9–11 am",sentWindow)
        Assert.assertTrue(model.state.value.info.orEmpty().contains("does not report delivery"))
        val restored = vm(); restored.send(); Assert.assertEquals(1,messages); Assert.assertTrue(restored.state.value.draft.accepted)
    }
    @Test fun freshDisabledSmsSettingPreventsRequest() {
        enabled = false
        val model = vm(); model.window("9–11 am"); model.send(); compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertEquals(0,messages); Assert.assertFalse(model.state.value.uncertain)
        Assert.assertTrue(model.state.value.error.orEmpty().contains("disabled"))
    }
    @Test fun unknownArrivalResultRequiresCustomerCheckAfterRecreation() {
        failSend = true
        val model = vm(); model.window("9–11 am"); model.send(); compose.waitUntil(10_000) { !model.state.value.busy }
        val restored = vm(); Assert.assertTrue(restored.state.value.uncertain); restored.send(); Assert.assertEquals(1,messages)
        restored.checkedCustomer(); Assert.assertFalse(restored.state.value.uncertain)
        Assert.assertEquals("9–11 am",restored.state.value.draft.window)
    }
    @Test fun missingPhoneBlocksArrivalMessageWithoutWrite() {
        phone = ""
        val model = vm(); model.window("9–11 am"); model.send()
        Assert.assertEquals(0,messages); Assert.assertTrue(model.state.value.error.orEmpty().contains("phone number"))
    }
}
