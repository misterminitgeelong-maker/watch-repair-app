package au.mainspring.nativeapp

import android.app.Application
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.MainspringAppShell
import au.mainspring.nativeapp.ui.screens.LoginScreen
import au.mainspring.nativeapp.ui.screens.ConsoleLandingScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*

class ShopSessionWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var site = "old-shop"
    private var switches = 0
    private var loginPath = ""
    private var oldHq = false
    private var oldPlatform = false
    private val sites = """[{"tenant_id":"old-shop","tenant_name":"Old Shop","tenant_slug":"old","user_id":"user-1","role":"manager"},{"tenant_id":"new-shop","tenant_name":"New Shop","tenant_slug":"new","user_id":"user-2","role":"tech"}]"""
    @Before fun setup() {
        androidx.test.platform.app.InstrumentationRegistry.getInstrumentation().targetContext.getSharedPreferences("more_usage", 0).edit().clear().commit()
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val body = when(request.path.orEmpty()) {
                    "/v1/auth/login", "/v1/auth/multi-site-login" -> {
                        loginPath = request.path!!
                        Assert.assertNull(request.getHeader("Authorization"))
                        """{"access_token":"old-access","refresh_token":"old-refresh"}"""
                    }
                    "/v1/auth/session/site" -> {
                        switches++; site = JsonParser.parseString(request.body.readUtf8()).asJsonObject["tenant_id"].asString
                        """{"access_token":"$site-access","refresh_token":"$site-refresh"}"""
                    }
                    "/v1/auth/session" -> """{"tenant_id":"$site","tenant_slug":"$site","plan_code":"test","enabled_features":[],"is_minit_hq_ui":${oldHq && site == "old-shop"},"is_platform_console":${oldPlatform && site == "old-shop"},"schedule_calendar_timezone":"Australia/Sydney","active_site_tenant_id":"$site","available_sites":$sites,"user":{"id":"${if(site == "old-shop") "user-1" else "user-2"}","full_name":"Operator","role":"${if(site == "old-shop") "manager" else "tech"}"}}"""
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setBody(body).setHeader("Content-Type","application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString())
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun auth() = AuthViewModel(InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as Application)
    private fun signedIn() = auth().also { model -> model.login("old","operator@example.test","test-password"); compose.waitUntil(10_000) { model.state.value.loggedIn } }
    @Test fun nativeLoginAllowsBlankShopIdAndUsesEmailOnlyEndpoint() {
        val model = auth()
        compose.setContent { val state by model.state.collectAsState(); MainspringTheme { LoginScreen(state,server.url("/").toString(),model::login) } }
        compose.onNodeWithText("Email").performTextInput("operator@example.test")
        compose.onNodeWithText("Password").performTextInput("test-password")
        compose.onNodeWithText("Sign in").performScrollTo().assertIsEnabled().performClick()
        compose.waitUntil(10_000) { model.state.value.loggedIn }
        Assert.assertEquals("/v1/auth/multi-site-login",loginPath); Assert.assertEquals(2,model.state.value.sites.size)
    }
    @Test fun drawerShopSwitchResetsSessionKeyAndKeepsDraftsInTheirOriginalShop() {
        val model = signedIn(); val oldKey = model.state.value.sessionKey
        TokenStore.bindDrafts().saveMessageDraft("unfinished","Old shop's draft")
        compose.setContent { val state by model.state.collectAsState(); MainspringTheme {
            key(state.sessionKey) { MainspringAppShell(state.sessionSummary,server.url("/").toString(),{},state.features,
                sites = state.sites,activeSiteId = state.activeSiteId,onSwitchSite = model::switchSite) }
        } }
        compose.onNodeWithTag("nav-more").performClick(); compose.onNodeWithTag("more-list").performScrollToNode(hasTestTag("more-group-settings"));compose.onNodeWithTag("more-group-settings").performClick(); compose.onNodeWithTag("more-list").performScrollToNode(androidx.compose.ui.test.hasText("Switch shop")); compose.onAllNodesWithText("Switch shop").onFirst().performClick()
        compose.onNodeWithText("New Shop").performClick()
        compose.waitUntil(10_000) { model.state.value.activeSiteId == "new-shop" && !model.state.value.loading }
        Assert.assertNotEquals(oldKey,model.state.value.sessionKey); Assert.assertEquals("",TokenStore.bindDrafts().loadMessageDraft("unfinished"))
        Assert.assertFalse(TokenStore.canManageInvoices()); Assert.assertEquals(1,switches)
        model.switchSite("old-shop"); compose.waitUntil(10_000) { model.state.value.activeSiteId == "old-shop" && !model.state.value.loading }
        Assert.assertEquals("Old shop's draft",TokenStore.bindDrafts().loadMessageDraft("unfinished")); Assert.assertEquals(2,switches)
    }
    @Test fun unlistedShopCannotTriggerAnExchangeRequest() {
        val model = signedIn(); model.switchSite("unlisted-shop")
        Assert.assertEquals(0,switches); Assert.assertEquals("old-shop",model.state.value.activeSiteId)
    }
    @Test fun authoritativeHqFlagOffersShopChoiceAndSwitchesToNativeShopContext() {
        oldHq = true
        val model = signedIn(); Assert.assertTrue(model.state.value.consoleOnly)
        compose.setContent { val state by model.state.collectAsState(); MainspringTheme { ConsoleLandingScreen(state,model::switchSite,{}, {}) } }
        compose.onNodeWithText("Open New Shop").performClick()
        compose.waitUntil(10_000) { model.state.value.activeSiteId == "new-shop" && !model.state.value.loading }
        Assert.assertFalse(model.state.value.consoleOnly)
    }
    @Test fun platformWorkspaceDoesNotPresentCounterIntakeActions() {
        oldPlatform = true
        val model = signedIn(); var webOpened = false
        Assert.assertTrue(model.state.value.consoleOnly)
        compose.setContent { MainspringTheme { ConsoleLandingScreen(model.state.value,{}, { webOpened = true }, {}) } }
        compose.onNodeWithText("New job").assertDoesNotExist()
        compose.onNodeWithText("Open web console").performClick(); Assert.assertTrue(webOpened)
    }
}
