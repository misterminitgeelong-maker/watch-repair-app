package au.mainspring.nativeapp

import android.app.Application
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert
import org.junit.Before
import org.junit.Rule
import org.junit.Test

/** Opening the app with no signal keeps the saved session and the shell; a real sign-out (401) still goes to sign-in. */
class ColdStartOfflineTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var sessionStatus = 200
    private val session = """{"tenant_id":"shop-1","tenant_slug":"cold","plan_code":"pro","enabled_features":["watch"],"is_minit_hq_ui":false,"is_platform_console":false,"schedule_calendar_timezone":"Australia/Sydney","active_site_tenant_id":"shop-1","available_sites":[],"user":{"id":"user-1","full_name":"Cold Start","role":"owner"}}"""

    private fun app() = InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as Application
    private fun auth() = AuthViewModel(app())
    private fun waitLoaded(model: AuthViewModel) = compose.waitUntil(10_000) { !model.state.value.loading }

    @Before fun setup() {
        TokenStore.init(app()); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when(request.path.orEmpty()) {
                "/v1/auth/session" -> MockResponse().setResponseCode(sessionStatus).setHeader("Content-Type", "application/json").setBody(if(sessionStatus == 200) session else "{}")
                "/v1/auth/refresh" -> MockResponse().setResponseCode(if(sessionStatus == 401) 401 else 503)  // a really expired session is refused by the refresh call too
                else -> MockResponse().setResponseCode(404)
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.saveTokens("access-1", "refresh-1")
    }
    @After fun cleanup() { TokenStore.clear(); try { server.shutdown() } catch(_: Exception) {} }

    @Test fun noSignalOnColdStartOpensFromTheSavedSessionAndRetriesWhenTheServerReturns() {
        val online = auth(); waitLoaded(online)
        Assert.assertTrue(online.state.value.loggedIn); Assert.assertFalse(online.state.value.offline)
        Assert.assertNotNull(TokenStore.sessionCache())

        sessionStatus = 503
        val offline = auth(); waitLoaded(offline)
        Assert.assertTrue("stays signed in", offline.state.value.loggedIn)
        Assert.assertTrue(offline.state.value.offline)
        Assert.assertEquals(setOf("watch"), offline.state.value.features); Assert.assertEquals("owner", offline.state.value.role)
        Assert.assertNotNull("tokens are kept", TokenStore.getAccessToken())

        sessionStatus = 200
        // The background retry runs on a timer as well as on reconnect, so the monitor does not need to flip here.
        compose.waitUntil(40_000) { !offline.state.value.offline }
        Assert.assertTrue(offline.state.value.loggedIn)
    }

    @Test fun expiredSessionStillGoesToSignInWithWelcomeBack() {
        val online = auth(); waitLoaded(online)
        sessionStatus = 401
        val ended = auth(); waitLoaded(ended)
        Assert.assertFalse(ended.state.value.loggedIn)
        Assert.assertNull(TokenStore.getAccessToken())
    }

    @Test fun noSavedSessionAndNoSignalStillShowsSignIn() {
        sessionStatus = 503
        val first = auth(); waitLoaded(first)
        Assert.assertFalse(first.state.value.loggedIn)
        Assert.assertNotNull("tokens are still kept for the retry", TokenStore.getAccessToken())
    }
}
