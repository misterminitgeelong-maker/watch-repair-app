package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.TenantEventLogRead
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class InboxActionsTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<String>()
    private var deleted = false

    private fun event(id: String, type: String = "quote_approved", entity: String = "repair_job", entityId: String = "job-$id") =
        """{"id":"$id","tenant_id":"t","event_type":"$type","event_summary":"Summary $id","created_at":"2026-10-01T00:00:00Z","entity_type":"$entity","entity_id":"$entityId"}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                requests.add(request.method + " " + path)
                val json = { b: String -> MockResponse().setHeader("Content-Type", "application/json").setBody(b) }
                return when {
                    path == "/v1/inbox/count" -> json("""{"count":${if (deleted) 1 else 2}}""")
                    path == "/v1/inbox" -> {
                        val offset = request.requestUrl!!.queryParameter("offset")!!.toInt()
                        if (offset == 0) json("[" + (1..InboxViewModel.PAGE_SIZE).joinToString(",") { event("e$it") } + "]")
                        else json("[" + event("older") + "]")
                    }
                    request.method == "DELETE" && path.startsWith("/v1/inbox/") -> { deleted = true; MockResponse().setResponseCode(204) }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun routesFollowEntityTypes() {
        fun ev(type: String, entity: String?, id: String? = "x") = TenantEventLogRead("1", null, type, "s", "d", entity, id)
        Assert.assertEquals("watchJob/x", inboxRoute(ev("quote_approved", "repair_job")))
        Assert.assertEquals("shoeJob/x", inboxRoute(ev("quote_approved", "shoe_repair_job")))
        Assert.assertEquals("autoKeyJob/x", inboxRoute(ev("quote_approved", "auto_key_job")))
        Assert.assertEquals("invoice/x", inboxRoute(ev("invoice_paid", "invoice")))
        Assert.assertEquals("messages/repair-jobs/x", inboxRoute(ev("customer_sms_reply", "repair_job")))
        Assert.assertEquals("messages/auto-key-jobs/x", inboxRoute(ev("customer_sms_reply", "auto_key_job")))
        Assert.assertNull(inboxRoute(ev("hq_enter_shop", "tenant")))
        Assert.assertNull(inboxRoute(ev("quote_approved", "repair_job", null)))
    }

    @Test fun pagingAndDeleteUpdateListAndCount() {
        val model = InboxViewModel(); compose.waitUntil(10_000) { !model.state.value.loading && model.state.value.events.isNotEmpty() }
        Assert.assertTrue(model.state.value.canLoadMore)
        model.loadMore(); compose.waitUntil(10_000) { !model.state.value.loadingMore }
        Assert.assertEquals(InboxViewModel.PAGE_SIZE + 1, model.state.value.events.size)
        Assert.assertFalse(model.state.value.canLoadMore)
        model.delete("older"); compose.waitUntil(10_000) { model.state.value.events.none { it.id == "older" } }
        Assert.assertTrue(requests.contains("DELETE /v1/inbox/older"))
        compose.waitUntil(10_000) { InboxCountStore.count.value == 1 }
    }
}
