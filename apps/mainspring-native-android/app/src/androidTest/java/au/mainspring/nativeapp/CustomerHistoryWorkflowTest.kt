package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.lifecycle.SavedStateHandle
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.MainspringAppShell
import au.mainspring.nativeapp.ui.screens.CustomerDetailScreen
import au.mainspring.nativeapp.ui.screens.MobileIntakeScreen
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class CustomerHistoryWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val paths = ConcurrentLinkedQueue<String>()
    private val customer = """{"id":"customer-1","full_name":"Avery Customer","created_at":"2026-10-07T00:00:00Z"}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                paths.add(request.path.orEmpty())
                val path = request.path.orEmpty().substringBefore('?')
                val body = when(path) {
                    "/v1/customers/customer-1" -> customer
                    "/v1/customers" -> "[$customer]"
                    "/v1/watches" -> "[]"
                    "/v1/repair-jobs" -> {
                        request.requestUrl!!.queryParameter("customer_id")?.let { Assert.assertEquals("customer-1", it) }
                        val older = request.requestUrl!!.queryParameter("offset") == "50"
                        (if(older) 51..51 else 1..50).joinToString(",","[","]") { n -> """{"id":"watch-job-$n","job_number":"W$n","title":"Watch repair $n","status":"awaiting_quote"}""" }
                    }
                    "/v1/shoe-repair-jobs" -> { request.requestUrl!!.queryParameter("customer_id")?.let { Assert.assertEquals("customer-1", it) }; """[{"id":"shoe-job","job_number":"S001","title":"Counter shoe repair","status":"awaiting_go_ahead"}]""" }
                    "/v1/auto-key-jobs" -> { request.requestUrl!!.queryParameter("customer_id")?.let { Assert.assertEquals("customer-1", it) }; """[{"id":"mobile-job","job_number":"M001","title":"Mobile replacement key","status":"awaiting_quote"}]""" }
                    "/v1/customer-accounts", "/v1/shoe-catalogue/items" -> "[]"
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setBody(body).setHeader("Content-Type","application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("history","operator"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun vm(features: Set<String> = setOf("watch","shoe","auto_key")) = CustomerDetailViewModel("customer-1",features).also { model -> compose.waitUntil(10_000) { !model.state.value.loading } }
    @Test fun allServiceHistoriesStayCustomerScopedAndOpenTheirOwnJobType() {
        val model = vm(); var opened = ""
        compose.setContent { MainspringTheme { CustomerDetailScreen("customer-1", {}, {}, {}, {}, features = setOf("watch","shoe","auto_key"),
            onOpenShoeJob = { opened = it }, onOpenMobileJob = { opened = it }, vm = model) } }
        compose.onNode(hasScrollAction()).performScrollToNode(hasText("Counter shoe repair"))
        compose.onNodeWithText("Counter shoe repair").performClick(); Assert.assertEquals("shoe-job",opened)
        compose.onNode(hasScrollAction()).performScrollToNode(hasText("Mobile replacement key"))
        compose.onNodeWithText("Mobile replacement key").performClick(); Assert.assertEquals("mobile-job",opened)
    }
    @Test fun olderWatchHistoryUsesCustomerIdAndOffsetRatherThanTruncatingAtFifty() {
        val model = vm(); Assert.assertTrue("watch" in model.state.value.more)
        model.loadMore("watch"); compose.waitUntil(10_000) { model.state.value.paging == null }
        Assert.assertEquals(51,model.state.value.watchJobs.size); Assert.assertFalse("watch" in model.state.value.more)
        Assert.assertTrue(paths.any { it.contains("customer_id=customer-1") && it.contains("offset=50") })
    }
    @Test fun mobileOnlyCustomerProfileSkipsWatchAndShoeEndpoints() {
        val model = vm(setOf("auto_key"))
        compose.setContent { MainspringTheme { CustomerDetailScreen("customer-1", {}, {}, {}, {}, features = setOf("auto_key"),vm = model) } }
        compose.onNodeWithText("New mobile job").assertExists(); compose.onNodeWithText("New watch repair").assertDoesNotExist()
        Assert.assertFalse(paths.any { it.startsWith("/v1/watches") || it.startsWith("/v1/repair-jobs") || it.startsWith("/v1/shoe-repair-jobs") })
    }
    @Test fun nativeCustomerRouteStartsMobileIntakeWithTheSelectedCustomer() {
        compose.setContent { MainspringTheme { MainspringAppShell(null,server.url("/").toString(),{},setOf("auto_key")) } }
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithText("People & network").performClick()
        compose.onNodeWithText("Customers").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Avery Customer").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithText("Avery Customer").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("New mobile job").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithText("New mobile job").performClick()
        compose.onNodeWithText("Job title *").assertExists()
        val restored = MobileIntakeViewModel(SavedStateHandle()); Assert.assertEquals("customer-1",restored.field("customerId"))
    }
    @Test fun preselectionDoesNotReplaceAnExistingMobileDraft() {
        val model = MobileIntakeViewModel(SavedStateHandle()); model.set("customerId","earlier-customer"); model.set("title","Earlier work")
        compose.setContent { MainspringTheme { MobileIntakeScreen({}, {}, model, preselectedCustomerId = "customer-1") } }
        compose.waitForIdle()
        Assert.assertEquals("earlier-customer",model.field("customerId")); Assert.assertEquals("Earlier work",model.field("title"))
    }
}
