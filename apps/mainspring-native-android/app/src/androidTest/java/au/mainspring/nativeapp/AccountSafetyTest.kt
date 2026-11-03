package au.mainspring.nativeapp

import android.app.Application
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.SignOutClient
import au.mainspring.nativeapp.ui.SubscriptionNotice
import au.mainspring.nativeapp.ui.screens.DeletionScope
import au.mainspring.nativeapp.ui.screens.deletionConfirmed
import au.mainspring.nativeapp.ui.screens.deletionRequestBody
import au.mainspring.nativeapp.ui.subscriptionNotice
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert
import org.junit.Before
import org.junit.Test
import java.time.Instant
import java.util.concurrent.TimeUnit

class AccountSafetyTest {
    private lateinit var server: MockWebServer
    private val seen = java.util.concurrent.ConcurrentLinkedQueue<String>()

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                seen.add("${request.method} ${request.path} ${request.getHeader("Authorization").orEmpty()}")
                return MockResponse().setResponseCode(if(request.path.orEmpty().startsWith("/v1/me/devices")) 204 else 200).setHeader("Content-Type", "application/json").setBody(if(request.path == "/v1/auth/logout") """{"revoked":1}""" else "")
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString())
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun waitFor(count: Int) { val end = System.currentTimeMillis() + 10_000; while(seen.size < count && System.currentTimeMillis() < end) Thread.sleep(20) }

    @Test fun signOutRevokesServerSessionAndClearsTokens() {
        TokenStore.saveTokens("acc-1", "ref-1")
        val model = AuthViewModel(InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as Application)
        model.logout()
        Assert.assertNull(TokenStore.getAccessToken()); Assert.assertNull(TokenStore.getRefreshToken())
        waitFor(1)
        Assert.assertEquals(listOf("POST /v1/auth/logout Bearer acc-1"), seen.toList())
    }

    @Test fun signOutUnregistersDeviceBeforeLogoutWhenATokenIsStored() {
        TokenStore.saveTokens("acc-2", "ref-2"); TokenStore.saveDeviceToken("device-token-abcdefghijklmnop")
        val model = AuthViewModel(InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as Application)
        model.logout()
        Assert.assertNull(TokenStore.deviceToken())
        waitFor(2)
        Assert.assertEquals(listOf("DELETE /v1/me/devices?token=device-token-abcdefghijklmnop Bearer acc-2", "POST /v1/auth/logout Bearer acc-2"), seen.toList())
    }

    @Test fun signOutStillClearsLocallyWhenServerIsUnreachable() = runBlocking {
        val base = server.url("/").toString(); server.shutdown()
        SignOutClient.revoke(base, "acc-3", "device-token-abcdefghijklmnop") // must not throw
        TokenStore.saveTokens("acc-3", "ref-3")
        val model = AuthViewModel(InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as Application)
        model.logout()
        Assert.assertNull(TokenStore.getAccessToken())
        server = MockWebServer()
    }

    @Test fun rememberedShopIdSurvivesSignOutAndCanBeForgotten() {
        LoginPrefs.save("old-shop", true)
        TokenStore.saveTokens("acc-4", "ref-4"); TokenStore.clear()
        Assert.assertEquals("old-shop", LoginPrefs.rememberedShopId())
        LoginPrefs.save("old-shop", false)
        Assert.assertEquals("", LoginPrefs.rememberedShopId()); Assert.assertFalse(LoginPrefs.rememberEnabled())
        LoginPrefs.save("", true)
    }

    @Test fun subscriptionNoticeCoversTrialPastDueAndHiddenCases() {
        val now = Instant.parse("2026-10-01T00:00:00Z")
        Assert.assertEquals(SubscriptionNotice.TrialEnding(3), subscriptionNotice("trialing", "2026-10-03T06:00:00Z", "owner", now))
        Assert.assertNull(subscriptionNotice("trialing", "2026-09-30T00:00:00Z", "owner", now))
        Assert.assertEquals(SubscriptionNotice.PaymentPastDue, subscriptionNotice("past_due", null, "manager", now))
        Assert.assertNull(subscriptionNotice("past_due", null, "platform_admin", now))
        Assert.assertNull(subscriptionNotice("active", null, "owner", now)); Assert.assertNull(subscriptionNotice(null, null, "owner", now))
    }

    @Test fun deletionRequiresTypedConfirmationAndNamesTheScope() {
        Assert.assertFalse(deletionConfirmed(DeletionScope.OwnLogin, "acme", "delet"))
        Assert.assertTrue(deletionConfirmed(DeletionScope.OwnLogin, "acme", " delete "))
        Assert.assertFalse(deletionConfirmed(DeletionScope.WholeShop, "acme", "DELETE"))
        Assert.assertTrue(deletionConfirmed(DeletionScope.WholeShop, "acme", "acme"))
        val body = deletionRequestBody(DeletionScope.WholeShop, "Acme Watches", "acme", "owner@example.test")
        Assert.assertTrue(body.contains("WHOLE SHOP") && body.contains("Shop ID: acme") && body.contains("owner@example.test"))
    }
}
