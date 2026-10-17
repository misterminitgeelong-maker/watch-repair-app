package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class MobileJobAdminTest {
    private lateinit var server: MockWebServer
    /** "METHOD path|expected-updated-at|body"; ConcurrentLinkedQueue cannot hold nulls so every entry is a non-null string. */
    private val requests = ConcurrentLinkedQueue<String>()
    private var deleteCode = 204
    private var updated = "2026-10-07T00:00:00Z"

    private fun job(extra: String = "") = """{"id":"job-1","job_number":"M001","title":"Replacement key","status":"booked","updated_at":"$updated","programming_status":"pending","priority":"normal","deposit_cents":2550,"cost_cents":0,"commission_lead_source":"shop_referred","job_type":"Diagnostic","key_quantity":1,"created_at":"2026-10-07T00:00:00Z","tenant_id":"t","customer_id":"c","status_token":"x","vehicle_make":"Toyota","vehicle_model":"Hilux","tech_notes":"Bring blade"$extra}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty()
                requests.add("${request.method} $path|${request.getHeader("X-Expected-Updated-At").orEmpty()}|${request.body.readUtf8()}")
                val json = { body: String -> MockResponse().setBody(body).setHeader("Content-Type", "application/json") }
                return when {
                    request.method == "DELETE" -> MockResponse().setResponseCode(deleteCode)
                    path.startsWith("/v1/auto-key-jobs/job-1/activity") -> json("""[{"id":"a","event_type":"auto_key_job_updated","event_summary":"Updated key type","created_at":"2026-10-07T01:00:00Z","actor_email":"t@x.au"},{"id":"b","event_type":"created","event_summary":"Job created","created_at":"2026-10-07T00:00:00Z"}]""")
                    path.endsWith("/clone") -> json(job().replace("\"id\":\"job-1\"", "\"id\":\"job-2\"").replace("M001", "M002"))
                    path.startsWith("/v1/vehicle-key-specs/search") -> json("""{"matches":[{"label":"Toyota Hilux 2016-2021","vehicle_make":"Toyota","vehicle_model":"Hilux","year_from":2016,"key_type":"Smart key","chip_type":"H","tech_notes":"Needs BSU","suggested_blade_code":"TOY48","bsu_required":true}]}""")
                    path.startsWith("/v1/vehicle-key-specs/job-context") -> json("{}")
                    request.method == "PATCH" -> { updated = "2026-10-07T00:05:00Z"; json(job()) }
                    path.startsWith("/v1/attachments") || path.startsWith("/v1/users") -> json("[]")
                    else -> json(job())
                }
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("admin", "operator"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun detail() = AutoKeyJobDetailViewModel("job-1", server.url("/").toString()).also { m -> waitFor { !m.state.value.loading } }
    private fun waitFor(timeoutMs: Long = 10_000, condition: () -> Boolean) {
        val end = System.currentTimeMillis() + timeoutMs
        while(!condition()) { if(System.currentTimeMillis() > end) Assert.fail("Timed out"); Thread.sleep(25) }
    }

    @Test fun activityLoadsNewestFirst() {
        val m = detail(); m.loadActivity(); waitFor { m.state.value.activityLoaded }
        Assert.assertEquals(listOf("a", "b"), m.state.value.activity.map { it.id })
        Assert.assertTrue(requests.any { it.startsWith("GET /v1/auto-key-jobs/job-1/activity?limit=100") })
    }

    @Test fun duplicateReturnsNewJob() {
        val m = detail(); m.duplicate(); waitFor { m.state.value.duplicated != null }
        Assert.assertEquals("M002", m.state.value.duplicated!!.jobNumber)
        Assert.assertTrue(requests.any { it.startsWith("POST /v1/auto-key-jobs/job-1/clone") })
    }

    @Test fun deleteMarksDeletedForOwnersOnly() {
        TokenStore.setSessionRole("tech")
        val blocked = detail(); blocked.deleteJob(); Thread.sleep(300)
        Assert.assertFalse(blocked.state.value.deleted); Assert.assertTrue(requests.none { it.startsWith("DELETE") })
        TokenStore.setSessionRole("manager")
        val m = detail(); m.deleteJob(); waitFor { m.state.value.deleted }
        Assert.assertTrue(requests.any { it.startsWith("DELETE /v1/auto-key-jobs/job-1") })
    }

    @Test fun failedDeleteKeepsJobAndReportsError() {
        deleteCode = 500
        val m = detail(); m.deleteJob(); waitFor { !m.state.value.adminBusy && m.state.value.adminError != null }
        Assert.assertFalse(m.state.value.deleted)
    }

    @Test fun keySearchThenApplyPatchesJobWithVersionHeader() {
        val m = detail(); m.searchKeys("Toyota", "Hilux", "2018"); waitFor { m.state.value.keySearched }
        val match = m.state.value.keyMatches.single(); Assert.assertEquals(true, match.bsuRequired); Assert.assertEquals(listOf("TOY48"), match.blankCodes())
        Assert.assertTrue(requests.any { it.contains("/v1/vehicle-key-specs/search?make=Toyota&model=Hilux&year=2018") })
        m.applyKeyMatch(match, "2018"); waitFor { m.state.value.keyApplied }
        val patch = requests.first { it.startsWith("PATCH") }.split("|", limit = 3)
        Assert.assertEquals("2026-10-07T00:00:00Z", patch[1])
        val body = JsonParser.parseString(patch[2]).asJsonObject
        Assert.assertEquals("Smart key", body["key_type"].asString); Assert.assertEquals("H", body["chip_type"].asString)
        Assert.assertEquals("TOY48", body["blade_code"].asString); Assert.assertEquals(2018, body["vehicle_year"].asInt)
        Assert.assertEquals("Bring blade\n\nNeeds BSU", body["tech_notes"].asString)
    }

    @Test fun shortKeySearchIsRejectedWithoutRequest() {
        val m = detail(); requests.clear(); m.searchKeys("T", "", "")
        Assert.assertNotNull(m.state.value.keySearchError); Assert.assertTrue(requests.isEmpty())
    }

    @Test fun statusPickerOffersOnHoldAndAcceptsIt() {
        Assert.assertTrue(au.mainspring.nativeapp.api.MOBILE_STATUS_PICKER.any { it.first == "booking_on_hold" })
        Assert.assertEquals("booking_on_hold", au.mainspring.nativeapp.api.canonicalMobileStatus("awaiting_parts"))
        val m = detail(); m.setStatus("booking_on_hold", "Waiting on blank"); waitFor { requests.any { it.startsWith("POST /v1/auto-key-jobs/job-1/status") } }
        Assert.assertTrue(requests.first { it.startsWith("POST") }.contains("booking_on_hold"))
    }

    @Test fun editorSavesTypePriorityDepositAndSource() {
        val e = MobileEditorViewModel("job-1"); waitFor { !e.state.value.loading }
        Assert.assertEquals("25.50", e.state.value.fields["deposit"])
        e.set("job_type", "All Keys Lost"); e.set("priority", "urgent"); e.set("deposit", "40"); e.set("commission_lead_source", "tech_sourced")
        e.save(); waitFor { e.state.value.saved }
        val body = JsonParser.parseString(requests.first { it.startsWith("PATCH") }.split("|", limit = 3)[2]).asJsonObject
        Assert.assertEquals("All Keys Lost", body["job_type"].asString); Assert.assertEquals("urgent", body["priority"].asString)
        Assert.assertEquals(4000, body["deposit_cents"].asInt); Assert.assertEquals("tech_sourced", body["commission_lead_source"].asString)
        Assert.assertFalse(body.has("deposit"))
    }

    @Test fun editorRejectsBadDeposit() {
        val e = MobileEditorViewModel("job-1"); waitFor { !e.state.value.loading }
        e.set("deposit", "abc"); e.save()
        Assert.assertTrue(e.state.value.error.orEmpty().startsWith("Deposit")); Assert.assertTrue(requests.none { it.startsWith("PATCH") })
    }
}
