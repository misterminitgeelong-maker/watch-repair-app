package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class ToolkitSettingsTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val patches = ConcurrentLinkedQueue<String>()
    private val catalogue = """{"enabled_categories":["vehicle_key"],"available_categories":[{"key":"vehicle_key","label":"Vehicle keys","description":"Keys"},{"key":"garage_door","label":"Garage doors","description":"Remotes"}]}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val json = { body: String -> MockResponse().setHeader("Content-Type", "application/json").setBody(body) }
                return when {
                    path == "/v1/toolkit/catalog" -> json("""{"groups":[],"scenarios":[]}""")
                    path == "/v1/toolkit/my-selection" -> json("""{"tool_keys":[]}""")
                    path == "/v1/toolkit/mobile-notifications" && request.method == "GET" -> json("""{"customer_sms_enabled":true,"dispatch_phone":"0400 000 000"}""")
                    path == "/v1/toolkit/mobile-notifications" && request.method == "PATCH" -> { val b = request.body.readUtf8(); patches.add("n:$b")
                        val o = JsonParser.parseString(b).asJsonObject
                        json("""{"customer_sms_enabled":${if(o.has("customer_sms_enabled")) o.get("customer_sms_enabled").asBoolean else true},"dispatch_phone":${if(o.has("dispatch_phone") && !o.get("dispatch_phone").isJsonNull) "\"" + o.get("dispatch_phone").asString + "\"" else "null"}}""") }
                    path == "/v1/toolkit/mobile-catalogue" && request.method == "GET" -> json(catalogue)
                    path == "/v1/toolkit/mobile-catalogue" && request.method == "PATCH" -> { patches.add("c:" + request.body.readUtf8())
                        json(catalogue.replace("""["vehicle_key"]""", """["vehicle_key","garage_door"]""")) }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString())
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun model(role: String): ToolkitViewModel { TokenStore.setDraftScope("toolkit", role); TokenStore.setSessionRole(role)
        return ToolkitViewModel().also { vm -> compose.waitUntil(10_000) { vm.settings.value.loaded } } }

    @Test fun ownerEditsSmsPhoneAndCategories() {
        val vm = model("owner"); Assert.assertEquals("0400 000 000", vm.settings.value.dispatchPhone)
        vm.setSms(false); compose.waitUntil(10_000) { patches.size >= 1 && !vm.settings.value.busy }
        Assert.assertEquals("""n:{"customer_sms_enabled":false}""", patches.first()); Assert.assertFalse(vm.settings.value.smsEnabled)
        vm.phoneDraft("  "); vm.saveDispatchPhone(); compose.waitUntil(10_000) { patches.size >= 2 && !vm.settings.value.busy }
        Assert.assertEquals("""n:{"dispatch_phone":null}""", patches.last()); Assert.assertEquals("", vm.settings.value.dispatchPhone)
        vm.toggleCategory("garage_door"); compose.waitUntil(10_000) { patches.size >= 3 && !vm.settings.value.busy }
        Assert.assertEquals("""c:{"enabled_categories":["vehicle_key","garage_door"]}""", patches.last())
        Assert.assertEquals(setOf("vehicle_key", "garage_door"), vm.settings.value.enabledCategories)
    }

    @Test fun techIsReadOnlyAndSendsNothing() {
        val vm = model("tech")
        Assert.assertFalse(vm.settings.value.canEditNotifications); Assert.assertFalse(vm.settings.value.canEditCatalogue)
        vm.setSms(false); vm.toggleCategory("garage_door"); Thread.sleep(500)
        Assert.assertTrue(patches.isEmpty()); Assert.assertTrue(vm.settings.value.smsEnabled)
    }

    @Test fun managerEditsNotificationsButNotCatalogue() {
        val vm = model("manager")
        Assert.assertTrue(vm.settings.value.canEditNotifications); Assert.assertFalse(vm.settings.value.canEditCatalogue)
    }
}
