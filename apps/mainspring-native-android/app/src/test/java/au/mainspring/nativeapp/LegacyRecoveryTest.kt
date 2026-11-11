package au.mainspring.nativeapp

import com.google.gson.Gson
import com.google.gson.JsonObject
import org.junit.Assert.*
import org.junit.Test

class LegacyRecoveryTest {
    private val job = "11111111-1111-4111-8111-111111111111"
    private fun write(url: String = "https://mainspring.au/v1/repair-jobs/$job/status", method: String = "post", body: String = """{"status":"completed"}""") = JsonObject().apply {
        addProperty("id", "22222222-2222-4222-8222-222222222222"); addProperty("idempotencyKey", "33333333-3333-4333-8333-333333333333")
        addProperty("url", url); addProperty("method", method); addProperty("body", body)
    }
    @Test fun targetParserKeepsTheOriginalBodyAndResolvesOnlyExistingJobWrites() {
        val target = legacyWriteTarget(write())!!
        assertEquals("v1/repair-jobs/$job", target.readPath); assertEquals("POST", target.method)
        assertEquals("completed", target.body["status"].asString)
        assertNotNull(legacyWriteTarget(write("/v1/shoe-repair-jobs/$job/note", body = """{"note":"Keep customer informed"}""")))
        assertNotNull(legacyWriteTarget(write("v1/auto-key-jobs/$job", "patch", """{"tech_notes":"Saved field notes"}""")))
    }
    @Test fun foreignHostsCredentialsQueriesCreatesPaymentsAndArbitraryPatchesCannotReplay() {
        for(url in listOf("https://other.test/v1/repair-jobs/$job/status", "//other.test/v1/repair-jobs/$job/status", "https://key@mainspring.au/v1/repair-jobs/$job/status", "https://mainspring.au:8443/v1/repair-jobs/$job/status", "https://mainspring.au/v1/repair-jobs/$job/status?tenant=other", "/v1/customers", "/v1/invoices/$job/payments")) assertNull(url, legacyWriteTarget(write(url)))
        assertNull(legacyWriteTarget(write("/v1/auto-key-jobs/$job", "patch", """{"cost_cents":1000}""")))
        assertNull(legacyWriteTarget(write(method = "DELETE")))
        assertNull(legacyWriteTarget(write(body = """{"status":"completed","tenant_id":"other"}""")))
    }
    @Test fun axiosDoubleEncodedBodyIsRecoveredButMissingOriginalRequestKeyIsRejected() {
        assertEquals("completed", legacyWriteTarget(write(body = Gson().toJson("""{"status":"completed"}""")))!!.body["status"].asString)
        assertNull(legacyWriteTarget(write().apply { remove("idempotencyKey") }))
        assertNull(legacyWriteTarget(write().apply { addProperty("expectedUpdatedAt", "injected\nheader") }))
    }
    @Test fun draftsAreStrictlyScopedAndExpiredEnvelopesArePreservedForRecovery() {
        fun envelope(scope: String) = Gson().toJson(mapOf("v" to 1, "kind" to "watch-intake", "scope" to scope, "savedAt" to 1, "data" to mapOf("job" to mapOf("title" to "Unfinished repair"))))
        val snapshot = JsonObject().apply { add("drafts", com.google.gson.JsonArray().apply {
            for(scope in listOf("tenant:user", "other:user", "tenant:other")) add(JsonObject().apply { addProperty("key", "mainspring.draft.v1.watch-intake.$scope"); addProperty("value", envelope(scope)) })
        }) }
        val mine = legacyDrafts(snapshot, "tenant", "user")
        assertEquals(1, mine.size); assertEquals("Unfinished repair", mine.single().data!!.getAsJsonObject("job")["title"].asString)
        assertTrue(legacyDrafts(snapshot, "tenant", "").isEmpty())
    }
}
