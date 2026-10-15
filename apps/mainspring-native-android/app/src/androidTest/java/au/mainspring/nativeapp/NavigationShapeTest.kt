package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.*
import okhttp3.mockwebserver.*
import org.junit.*

/** The bar and More follow the shop's service plan, keep Customers out of the bar, and More remembers what was opened. */
class NavigationShapeTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer

    @Before fun setup() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        ctx.getSharedPreferences("more_usage", 0).edit().clear().commit()
        TokenStore.init(ctx); TokenStore.clear(); TokenStore.setSessionRole("owner"); TokenStore.setDraftScope("nav-shop", "nav-user")
        TokenStore.setShopIdentity("AUD", "Native QA", "ABN", "0400000000", "Address")
        DesignPreferences.init(ctx); DesignPreferences.select(AppAppearance.CALIBRE)
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest) = MockResponse().setHeader("Content-Type", "application/json")
                .setBody(if(request.requestUrl!!.encodedPath.endsWith("/page") || request.requestUrl!!.encodedPath.endsWith("count")) """{"items":[],"total":0,"count":0}""" else "[]")
        }; server.start()
        TokenStore.saveApiBaseUrl(server.url("/").toString())
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun shell(features: Set<String>) = compose.setContent { MainspringTheme { MainspringAppShell("Native QA", server.url("/").toString(), {}, features) } }

    @Test fun barHasFourTabsAndNoCustomersTab() {
        shell(setOf("watch", "shoe", "auto_key"))
        listOf("nav-today", "nav-jobs", "nav-inbox", "nav-more").forEach { compose.onNodeWithTag(it).assertExists() }
        compose.onNodeWithTag("nav-people").assertDoesNotExist()
    }

    @Test fun watchOnlyShopSeesRepairsTabAndNoMobileGroup() {
        shell(setOf("watch"))
        compose.onNodeWithTag("nav-jobs").assertExists()
        compose.onNodeWithText("Repairs").assertExists()
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithTag("more-group-workshop").assertExists()
        compose.onNodeWithTag("more-group-mobile").assertDoesNotExist()
    }

    @Test fun mobileOnlyShopKeepsJobsLabelAndLeadsWithMobileGroup() {
        shell(setOf("auto_key"))
        compose.onNodeWithText("Jobs").assertExists()
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithTag("more-group-mobile").assertExists()
        compose.onNodeWithTag("more-group-workshop").assertDoesNotExist()
    }

    @Test fun groupsStartCollapsedExpandOnTapAndRememberThat() {
        shell(setOf("watch"))
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithText("Repair queue").assertDoesNotExist()
        compose.onNodeWithTag("more-group-workshop").performClick()
        compose.onNodeWithText("Repair queue").assertExists()
        val remembered = InstrumentationRegistry.getInstrumentation().targetContext.getSharedPreferences("more_usage", 0).getStringSet("expanded", null)
        Assert.assertEquals(setOf("workshop"), remembered)
        compose.onNodeWithTag("more-group-workshop").performClick()
        compose.onNodeWithText("Repair queue").assertDoesNotExist()
    }

    @Test fun searchFindsToolsAcrossCollapsedGroups() {
        shell(setOf("watch"))
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithTag("more-search").performTextInput("Invoic")
        compose.onNodeWithText("Invoices").assertExists()
        compose.onNodeWithTag("more-search").performTextReplacement("zzz")
        compose.onNodeWithText("No tool matches “zzz”.").assertExists()
    }

    @Test fun customersReachableFromMoreQuickAccess() {
        shell(setOf("watch"))
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithText("Customers").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithContentDescription("New customer").fetchSemanticsNodes().isNotEmpty() || compose.onAllNodesWithText("New customer").fetchSemanticsNodes().isNotEmpty() }
    }
}
