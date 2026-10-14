package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Payload checks for the watch job actions: customer-visible status note and technician assignment. */
class WatchJobActionsTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var status = "working_on"
    private var assignedUserId: String? = null
    // ConcurrentLinkedQueue cannot hold nulls, so every entry is a non-null "METHOD path body" string.
    private val requests = ConcurrentLinkedQueue<String>()

    private fun job(): String {
        val assigned = assignedUserId?.let { "\"$it\"" } ?: "null"
        return """{"id":"job-1","watch_id":"watch-1","job_number":"TEST-001","title":"Repair QA","status":"$status","priority":"normal","created_at":"2026-10-08T00:00:00Z","assigned_user_id":$assigned,"customer_phone":"0412345678","customer_email":"a@example.com"}"""
    }

    private fun bodiesFor(suffix: String, method: String = "POST"): List<JsonObject> =
        requests.filter { it.startsWith("$method ") && it.substringAfter(' ').substringBefore(' ').endsWith(suffix) }
            .map { JsonParser.parseString(it.substringAfter(' ').substringAfter(' ')).asJsonObject }

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = request.body.readUtf8()
                requests.add("${request.method} $path $body")
                val json = when {
                    request.method == "POST" && path.endsWith("/status") -> {
                        status = JsonParser.parseString(body).asJsonObject["status"].asString; job()
                    }
                    request.method == "PATCH" && path.endsWith("/job-1") -> {
                        val fields = JsonParser.parseString(body).asJsonObject
                        assignedUserId = if (fields["clear_assigned_user"]?.asBoolean == true) null else fields["assigned_user_id"]?.asString ?: assignedUserId
                        job()
                    }
                    request.method == "POST" && path.endsWith("/claim") -> job()
                    path.endsWith("/job-1") -> job()
                    path.endsWith("/watch-1") -> """{"id":"watch-1","tenant_id":"t","customer_id":"c","brand":"Seiko","model":"SKX007","serial_number":"123","movement_type":"Automatic","condition_notes":"Scratched crystal"}"""
                    path.endsWith("/v1/users") -> """[{"id":"user-2","full_name":"Tess Tech","role":"tech","is_active":true,"email":"t@example.com"}]"""
                    path.endsWith("/v1/quotes") -> """[{"id":"quote-1","repair_job_id":"job-1","status":"sent","subtotal_cents":100,"tax_cents":10,"total_cents":110,"currency":"AUD","approval_token":"tok-1","created_at":"2026-10-08T00:00:00Z"}]"""
                    path.endsWith("/resend") -> """{"id":"quote-1","status":"sent","sent_at":"2026-10-09T00:00:00Z","approval_token":"tok-2"}"""
                    else -> "[]"
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(json)
            }
        }; server.start()
        TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("tenant-1", "user-1"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun model() = JobDetailViewModel("job-1", server.url("/").toString()).also { compose.waitUntil(10_000) { !it.state.value.loading } }

    @Test fun statusChangeSendsStaffNoteAndCustomerNote() {
        val model = model()
        model.setStatus("completed", "Seal checked", "  Your watch is ready soon  ")
        compose.waitUntil(10_000) { !model.state.value.statusBusy && !model.state.value.loading }
        val sent = bodiesFor("/status").single()
        Assert.assertEquals("completed", sent["status"].asString)
        Assert.assertEquals("Seal checked", sent["note"].asString)
        Assert.assertEquals("Your watch is ready soon", sent["customer_note"].asString)
    }

    @Test fun statusChangeWithoutCustomerNoteOmitsTheField() {
        val model = model()
        model.setStatus("completed", "Seal checked")
        compose.waitUntil(10_000) { !model.state.value.statusBusy && !model.state.value.loading }
        Assert.assertFalse(bodiesFor("/status").single().has("customer_note"))
    }

    @Test fun customerNoteIsCappedAtBackendLimit() {
        val model = model()
        model.setStatus("completed", null, "x".repeat(400))
        compose.waitUntil(10_000) { !model.state.value.statusBusy && !model.state.value.loading }
        Assert.assertEquals(JobDetailViewModel.CUSTOMER_NOTE_MAX, bodiesFor("/status").single()["customer_note"].asString.length)
    }

    @Test fun thirdPartyStatusIsAcceptedAndWatchDetailsLoad() {
        val model = model()
        Assert.assertEquals("Seiko", model.state.value.watch?.brand)
        model.setStatus("at_third_party_repairer")
        compose.waitUntil(10_000) { !model.state.value.statusBusy && !model.state.value.loading }
        Assert.assertEquals("at_third_party_repairer", bodiesFor("/status").single()["status"].asString)
    }

    @Test fun assignSendsAssignedUserIdAndUnassignSendsClear() {
        val model = model(); model.loadUsers()
        compose.waitUntil(10_000) { model.state.value.users.isNotEmpty() }
        model.assignTechnician("user-2")
        compose.waitUntil(10_000) { !model.state.value.assignBusy }
        Assert.assertEquals("user-2", bodiesFor("/job-1", "PATCH").single()["assigned_user_id"].asString)
        Assert.assertEquals("user-2", model.state.value.job?.assignedUserId)
        model.assignTechnician(null)
        compose.waitUntil(10_000) { !model.state.value.assignBusy }
        val clear = bodiesFor("/job-1", "PATCH").last()
        Assert.assertTrue(clear["clear_assigned_user"].asBoolean); Assert.assertFalse(clear.has("assigned_user_id"))
        Assert.assertNull(model.state.value.job?.assignedUserId)
    }

    @Test fun claimAlsoAssignsTheJobToTheSignedInUser() {
        val model = model(); model.claimJob()
        compose.waitUntil(10_000) { !model.state.value.claimBusy }
        Assert.assertEquals("user-1", bodiesFor("/job-1", "PATCH").single()["assigned_user_id"].asString)
    }

    @Test fun quoteResendPostsAndKeepsTheNewApprovalToken() {
        val model = QuoteDetailViewModel("quote-1")
        compose.waitUntil(10_000) { !model.state.value.loading && model.state.value.quote != null }
        model.resendQuote()
        compose.waitUntil(10_000) { !model.state.value.resendBusy && model.state.value.info != null }
        Assert.assertEquals(1, requests.count { it.startsWith("POST /v1/quotes/quote-1/resend") })
        Assert.assertEquals("tok-2", model.state.value.quote?.approvalToken)
        Assert.assertEquals("https://example.test/approve/tok-2", au.mainspring.nativeapp.api.quoteApprovalLink("https://example.test/v1/", "tok-2"))
    }
}
