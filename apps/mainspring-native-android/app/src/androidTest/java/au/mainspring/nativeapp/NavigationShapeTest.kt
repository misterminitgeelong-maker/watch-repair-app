package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.*
import okhttp3.mockwebserver.*
import org.junit.*

/** The bar and More follow the shop's service plan: Home, Inbox, up to two service tabs, More with a tool grid. */
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

    @Test fun threeServicesShowTwoServiceTabsAndShoeMovesToMore() {
        shell(setOf("watch", "shoe", "auto_key"))
        listOf("nav-today", "nav-inbox", "nav-watch", "nav-mobile", "nav-more").forEach { compose.onNodeWithTag(it).assertExists() }
        listOf("nav-shoe", "nav-jobs", "nav-people").forEach { compose.onNodeWithTag(it).assertDoesNotExist() }
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithText("Shoe").assertExists()
        compose.onNodeWithText("All jobs").assertExists()
    }

    @Test fun twoServicesGetTwoTabs() {
        shell(setOf("watch", "shoe"))
        listOf("nav-watch", "nav-shoe").forEach { compose.onNodeWithTag(it).assertExists() }
        compose.onNodeWithTag("nav-mobile").assertDoesNotExist()
    }

    @Test fun watchOnlyShopSeesWatchTabAndNoMobileTools() {
        shell(setOf("watch"))
        compose.onNodeWithTag("nav-watch").assertExists()
        compose.onNodeWithTag("nav-mobile").assertDoesNotExist()
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithText("Workshop tools").assertExists()
        compose.onNodeWithText("Mobile tools").assertDoesNotExist()
        compose.onNodeWithText("Workshop tools").performClick()
        compose.onNodeWithText("Repair queue").assertExists()
    }

    @Test fun mobileOnlyShopHasMobileTabAndMobileTools() {
        shell(setOf("auto_key"))
        compose.onNodeWithTag("nav-mobile").assertExists()
        compose.onNodeWithTag("nav-watch").assertDoesNotExist()
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithText("Mobile tools").performClick()
        compose.onNodeWithText("Dispatch pool").assertExists()
    }

    @Test fun headerSearchIconIsOnTabScreens() {
        shell(setOf("watch"))
        compose.onNodeWithTag("app-search").assertExists()
    }

    @Test fun searchFindsToolsInTheGrid() {
        shell(setOf("watch"))
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithTag("more-search").performTextInput("Invoic")
        compose.onNodeWithText("Invoices").assertExists()
        compose.onNodeWithText("Quotes").assertDoesNotExist()
        compose.onNodeWithTag("more-search").performTextReplacement("zzz")
        compose.onNodeWithText("No tool matches \u201czzz\u201d.").assertExists()
    }

    @Test fun customersReachableFromMoreGrid() {
        shell(setOf("watch"))
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithText("Customers").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithContentDescription("New customer").fetchSemanticsNodes().isNotEmpty() || compose.onAllNodesWithText("New customer").fetchSemanticsNodes().isNotEmpty() }
    }

    @Test fun moreAlwaysOpensTheSheetEvenAfterOpeningATool() {
        shell(setOf("watch"))
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithText("Customers").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("New customer").fetchSemanticsNodes().isNotEmpty() || compose.onAllNodesWithContentDescription("New customer").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithTag("more-list").assertExists()
        compose.onNodeWithTag("nav-today").performClick()
        compose.onNodeWithTag("nav-today").assertIsSelected()
    }
}
