package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.AccountsScreen
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Owner-only Xero disconnect and Stripe payout status refresh on the native Account screen, against a mock server. */
class AccountsBillingActionsTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val posts = ConcurrentLinkedQueue<String>()
    @Volatile private var role = "owner"
    @Volatile private var xeroConnected = true
    @Volatile private var chargesEnabled = false

    private fun session() = """{"tenant_id":"t","tenant_slug":"shop","plan_code":"pro","enabled_features":[],"tenant_name":"Shop","user":{"id":"u","full_name":"Sam","email":"s@example.test","role":"$role"}}"""
    private fun limits() = """{"plan_code":"pro","limits":{},"usage":{},"stripe_configured":true,"xero_configured":true,"xero_connected":$xeroConnected,"stripe_connect_account_present":true,"stripe_connect_charges_enabled":$chargesEnabled,"stripe_connect_payouts_enabled":false,"stripe_connect_details_submitted":true}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath
                val json = MockResponse().setHeader("Content-Type", "application/json")
                return when {
                    path == "/v1/auth/session" -> json.setBody(session())
                    path == "/v1/billing/limits" -> json.setBody(limits())
                    path == "/v1/billing/xero/disconnect" -> { posts.add(path); xeroConnected = false; json.setBody("""{"configured":true,"connected":false,"connection_status":"disconnected"}""") }
                    path == "/v1/billing/connect/refresh" -> { posts.add(path); chargesEnabled = true; json.setBody("""{"stripe_connect_charges_enabled":true,"stripe_connect_payouts_enabled":false,"stripe_connect_details_submitted":true}""") }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("accounts", "owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun open(sessionRole: String) {
        role = sessionRole; TokenStore.setSessionRole(sessionRole)
        compose.setContent { MainspringTheme { AccountsScreen(onBack = {}, onSignOut = {}) } }
    }

    @Test fun ownerDisconnectsXeroAfterConfirming() {
        open("owner")
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("disconnect-xero").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("disconnect-xero").performScrollTo().performClick()
        compose.onNodeWithText("Disconnect Xero?").assertExists()
        Assert.assertTrue("nothing is sent before the owner confirms", posts.isEmpty())
        compose.onNodeWithTag("confirm-disconnect-xero").performClick()
        compose.waitUntil(10_000) { posts.isNotEmpty() }
        Assert.assertEquals("/v1/billing/xero/disconnect", posts.peek())
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Xero disconnected.").fetchSemanticsNodes().isNotEmpty() }
        compose.onAllNodesWithTag("disconnect-xero").assertCountEquals(0)
        compose.onNodeWithText("Not connected").assertExists()
    }

    @Test fun cancellingTheConfirmationSendsNothing() {
        open("owner")
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("disconnect-xero").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("disconnect-xero").performScrollTo().performClick()
        compose.onNodeWithText("Cancel").performClick()
        compose.waitForIdle()
        Assert.assertTrue(posts.isEmpty())
    }

    @Test fun ownerRefreshesPayoutStatusAndSeesTheNewState() {
        open("owner")
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("refresh-payouts").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithText("Card payments").assertExists()
        compose.onNodeWithTag("refresh-payouts").performScrollTo().performClick()
        compose.waitUntil(10_000) { posts.isNotEmpty() }
        Assert.assertEquals("/v1/billing/connect/refresh", posts.peek())
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("accounts-info").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("accounts-info").assertTextContains("Card payments are enabled.", substring = true)
        compose.onNodeWithText("Enabled").assertExists()
    }

    @Test fun managersCannotDisconnectXeroOrRefreshPayouts() {
        open("manager")
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Connected").fetchSemanticsNodes().isNotEmpty() }
        compose.onAllNodesWithTag("disconnect-xero").assertCountEquals(0)
        compose.onAllNodesWithTag("refresh-payouts").assertCountEquals(0)
    }
}
