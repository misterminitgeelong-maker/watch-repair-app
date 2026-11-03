package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.ShoeItemCreate
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Shoe job edits after intake: services, pairs and the customer-visible status note. */
class ShoeJobActionsTest {
    @get:Rule val compose = HeadlessRule()
    private lateinit var server: MockWebServer
    // ConcurrentLinkedQueue cannot hold nulls, so every entry is a non-null "METHOD path body" string.
    private val requests = ConcurrentLinkedQueue<String>()
    private fun job(extra: String = "") = """{"id":"job-1","tenant_id":"t","shoe_id":"shoe-1","job_number":"S-001","status_token":"x","title":"Resole","priority":"normal","status":"working_on","deposit_cents":0,"cost_cents":0,"quote_approval_token":"q","quote_status":"none","created_at":"2026-10-08T00:00:00Z","items":[{"id":"item-1","item_name":"Heel tips","unit_price_cents":2500,"quantity":1.0}],"shoe":{"id":"shoe-1","customer_id":"cust-1","shoe_type":"Boot","brand":"Blundstone","color":"Black","description_notes":"Scuffed toe"},"extra_shoes":[{"id":"entry-1","shoe_id":"shoe-2","sort_order":1,"shoe":{"id":"shoe-2","customer_id":"cust-1","shoe_type":"Heel"}}]$extra}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = request.body.readUtf8()
                requests.add("${request.method} $path $body")
                val json = when {
                    path.endsWith("/status-history") || path == "/v1/attachments" -> "[]"
                    path == "/v1/shoe-repair-jobs/shoes" -> """{"id":"shoe-9"}"""
                    else -> job()
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(json)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("shoe-actions", "tech"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun model() = ShoeJobDetailViewModel("job-1", server.url("/").toString()).also { compose.waitUntil(10_000) { !it.state.value.loading } }
    private fun idle(m: ShoeJobDetailViewModel) = compose.waitUntil(10_000) { !m.state.value.editBusy && !m.state.value.statusBusy && !m.state.value.loading }
    private fun writes() = requests.filter { !it.startsWith("GET") }

    @Test fun shoeDetailsParseForPrimaryAndExtraPairs() {
        val j = model().state.value.job!!
        Assert.assertEquals("Blundstone", j.shoe!!.brand); Assert.assertEquals("Black", j.shoe!!.color); Assert.assertEquals("Scuffed toe", j.shoe!!.notes)
        Assert.assertEquals("Heel", j.extraShoes!!.single().shoe!!.shoeType); Assert.assertEquals(2500, j.items.single().price)
    }
    @Test fun addServicesPostsItemsAndRemoveDeletesItem() {
        val m = model()
        m.addServices(listOf(ShoeItemCreate("k1", "g1", "Resole", "fixed", 8000, 1.0)))
        idle(m)
        val post = writes().single { it.startsWith("POST /v1/shoe-repair-jobs/job-1/items") }
        val item = JsonParser.parseString(post.substringAfter("items ")).asJsonObject["items"].asJsonArray[0].asJsonObject
        Assert.assertEquals("k1", item["catalogue_key"].asString); Assert.assertEquals(8000, item["unit_price_cents"].asInt)
        m.removeService("item-1"); idle(m)
        Assert.assertTrue(writes().any { it.startsWith("DELETE /v1/shoe-repair-jobs/job-1/items/item-1") })
    }
    @Test fun addPairCreatesShoeThenLinksAndRemovePairDeletesEntry() {
        val m = model()
        m.addPair("Sneaker", "Nike", "White", ""); idle(m)
        val w = writes()
        Assert.assertEquals(listOf("POST /v1/shoe-repair-jobs/shoes", "POST /v1/shoe-repair-jobs/job-1/shoes"), w.map { it.substringBefore(" {") })
        val created = JsonParser.parseString(w[0].substringAfter("shoes ")).asJsonObject
        Assert.assertEquals("cust-1", created["customer_id"].asString); Assert.assertEquals("Nike", created["brand"].asString)
        Assert.assertEquals("shoe-9", JsonParser.parseString(w[1].substringAfter("job-1/shoes ")).asJsonObject["shoe_id"].asString)
        m.removePair("entry-1"); idle(m)
        Assert.assertTrue(writes().any { it.startsWith("DELETE /v1/shoe-repair-jobs/job-1/shoes/entry-1") })
    }
    @Test fun statusChangeSendsTrimmedCustomerNoteCappedAt280() {
        val m = model()
        m.setStatus("completed", null, "  " + "x".repeat(300)); idle(m)
        val body = JsonParser.parseString(writes().first { it.contains("/status ") }.substringAfter("/status ")).asJsonObject
        Assert.assertEquals("completed", body["status"].asString); Assert.assertEquals(280, body["customer_note"].asString.length)
        Assert.assertFalse(body.has("note"))
    }
    @Test fun statusChangeWithoutCustomerNoteOmitsField() {
        val m = model(); m.setStatus("completed", "staff only"); idle(m)
        val body = JsonParser.parseString(writes().first { it.contains("/status ") }.substringAfter("/status ")).asJsonObject
        Assert.assertFalse(body.has("customer_note")); Assert.assertEquals("staff only", body["note"].asString)
    }
}
