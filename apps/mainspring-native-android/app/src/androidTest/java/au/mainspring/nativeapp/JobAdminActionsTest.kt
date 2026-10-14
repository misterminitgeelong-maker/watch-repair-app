package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.MobileQuoteLine
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Delete, duplicate, B2B account assignment and create-and-send quote for watch and shoe jobs. */
class JobAdminActionsTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    // ConcurrentLinkedQueue cannot hold nulls, so every entry is a non-null "METHOD path body" string.
    private val requests = ConcurrentLinkedQueue<String>()
    private var account: String? = null

    private fun watchJob(): String {
        val acc = account?.let { "\"$it\"" } ?: "null"
        return """{"id":"job-1","watch_id":"watch-1","job_number":"W-001","title":"Service","status":"working_on","priority":"normal","created_at":"2026-10-08T00:00:00Z","customer_account_id":$acc}"""
    }
    private fun shoeJob(): String {
        val acc = account?.let { "\"$it\"" } ?: "null"
        return """{"id":"sjob-1","tenant_id":"t","shoe_id":"shoe-1","job_number":"S-001","status_token":"x","title":"Resole","priority":"normal","status":"working_on","deposit_cents":0,"cost_cents":0,"quote_approval_token":"q","quote_status":"none","created_at":"2026-10-08T00:00:00Z","items":[],"customer_account_id":$acc}"""
    }
    private fun writes() = requests.filter { !it.startsWith("GET") }

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = request.body.readUtf8()
                requests.add("${request.method} $path $body")
                if (request.method == "DELETE") return MockResponse().setResponseCode(204)
                val json = when {
                    request.method == "PATCH" && path.endsWith("/job-1") -> {
                        account = JsonParser.parseString(body).asJsonObject["customer_account_id"].takeUnless { it.isJsonNull }?.asString; watchJob()
                    }
                    request.method == "PATCH" && path.endsWith("/sjob-1") -> {
                        account = JsonParser.parseString(body).asJsonObject["customer_account_id"].takeUnless { it.isJsonNull }?.asString; shoeJob()
                    }
                    request.method == "POST" && path.endsWith("/job-1/clone") -> """{"id":"job-2"}"""
                    request.method == "POST" && path.endsWith("/sjob-1/clone") -> """{"id":"sjob-2"}"""
                    request.method == "POST" && path == "/v1/quotes" -> """{"id":"quote-1","repair_job_id":"job-1","status":"draft","subtotal_cents":1000,"tax_cents":0,"total_cents":1000,"currency":"AUD","created_at":"2026-10-08T00:00:00Z"}"""
                    request.method == "POST" && path.endsWith("/quote-1/send") -> """{"id":"quote-1","status":"sent","sent_at":"2026-10-09T00:00:00Z","approval_token":"tok-1"}"""
                    path.endsWith("/job-1") -> watchJob()
                    path.endsWith("/sjob-1") -> shoeJob()
                    path.endsWith("/watch-1") -> """{"id":"watch-1","tenant_id":"t","customer_id":"c","brand":"Seiko"}"""
                    path.endsWith("/customer-accounts") -> """[{"id":"acc-1","name":"Acme","customer_ids":["c"],"is_active":true}]"""
                    else -> "[]"
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(json)
            }
        }; server.start()
        TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("tenant-1", "user-1"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun watch() = JobDetailViewModel("job-1", server.url("/").toString()).also { compose.waitUntil(10_000) { !it.state.value.loading } }
    private fun shoe() = ShoeJobDetailViewModel("sjob-1", server.url("/").toString()).also { compose.waitUntil(10_000) { !it.state.value.loading } }

    @Test fun ownerDeletesWatchJob() {
        val m = watch(); m.deleteJob()
        compose.waitUntil(10_000) { m.state.value.deleted }
        Assert.assertTrue(writes().any { it.startsWith("DELETE /v1/repair-jobs/job-1") })
    }
    @Test fun techCannotDeleteWatchOrShoeJob() {
        TokenStore.setSessionRole("tech")
        val w = watch(); w.deleteJob(); val s = shoe(); s.deleteJob()
        Assert.assertTrue(writes().none { it.startsWith("DELETE") })
        Assert.assertFalse(w.state.value.deleted); Assert.assertFalse(s.state.value.deleted)
    }
    @Test fun ownerDeletesShoeJob() {
        val m = shoe(); m.deleteJob()
        compose.waitUntil(10_000) { m.state.value.deleted }
        Assert.assertTrue(writes().any { it.startsWith("DELETE /v1/shoe-repair-jobs/sjob-1") })
    }
    @Test fun duplicateReturnsNewJobId() {
        val w = watch(); w.duplicateJob()
        compose.waitUntil(10_000) { w.state.value.clonedJobId != null }
        Assert.assertEquals("job-2", w.state.value.clonedJobId)
        Assert.assertTrue(writes().any { it.startsWith("POST /v1/repair-jobs/job-1/clone") })
        val s = shoe(); s.duplicateJob()
        compose.waitUntil(10_000) { s.state.value.clonedJobId != null }
        Assert.assertEquals("sjob-2", s.state.value.clonedJobId)
        Assert.assertTrue(writes().any { it.startsWith("POST /v1/shoe-repair-jobs/sjob-1/clone") })
    }
    @Test fun assignAndUnassignAccountOnWatchJob() {
        val m = watch(); m.loadAccounts()
        compose.waitUntil(10_000) { m.state.value.accounts.isNotEmpty() }
        m.assignAccount("acc-1")
        compose.waitUntil(10_000) { m.state.value.job?.customerAccountId == "acc-1" }
        m.assignAccount(null)
        compose.waitUntil(10_000) { m.state.value.job?.customerAccountId == null && !m.state.value.accountBusy }
        val bodies = writes().filter { it.startsWith("PATCH /v1/repair-jobs/job-1") }.map { JsonParser.parseString(it.substringAfter("job-1 ")).asJsonObject }
        Assert.assertEquals("acc-1", bodies[0]["customer_account_id"].asString)
        Assert.assertTrue(bodies[1].has("customer_account_id") && bodies[1]["customer_account_id"].isJsonNull)
    }
    @Test fun assignAccountOnShoeJob() {
        val m = shoe(); m.assignAccount("acc-1")
        compose.waitUntil(10_000) { m.state.value.job?.customerAccountId == "acc-1" }
        Assert.assertTrue(writes().any { it.startsWith("PATCH /v1/shoe-repair-jobs/sjob-1") && it.contains("acc-1") })
    }
    @Test fun createAndSendQuoteCreatesThenSends() {
        val m = JobQuotesViewModel("job-1"); compose.waitUntil(10_000) { !m.state.value.loading }
        m.createAndSendLines(listOf(MobileQuoteLine("Service", 1.0, 1000)), true, true)
        compose.waitUntil(10_000) { m.state.value.sentToCustomer && !m.state.value.busy }
        val w = writes().map { it.substringBefore(" {").trimEnd() }
        Assert.assertEquals(listOf("POST /v1/quotes", "POST /v1/quotes/quote-1/send"), w)
        Assert.assertEquals("sent", m.state.value.quotes.first().status)
    }
}
