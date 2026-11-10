package au.mainspring.nativeapp

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import androidx.core.content.FileProvider
import androidx.lifecycle.SavedStateHandle
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.MobileQuoteLine
import au.mainspring.nativeapp.ui.IntakeTicketCopy
import au.mainspring.nativeapp.ui.QrCode
import au.mainspring.nativeapp.ui.drawIntakeCopy
import au.mainspring.nativeapp.ui.paginateIntakeCopy
import au.mainspring.nativeapp.ui.wrapText
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.io.File
import java.util.concurrent.ConcurrentLinkedQueue

/** Native contracts against an isolated local server, including write conflicts and distinct photo labels. */
class WatchParityWorkflowTest {
    @get:Rule val wait = HeadlessRule()
    private lateinit var server: MockWebServer
    @Volatile private var notes: String? = "Original private notes"
    private val writes = ConcurrentLinkedQueue<Pair<String, String>>()
    private val photoLabels = ConcurrentLinkedQueue<String>()
    private val listOffsets = ConcurrentLinkedQueue<Int>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun job() = """{"id":"job-1","tenant_id":"tenant","watch_id":"watch-1","job_number":"W001","title":"Service","description":"Losing time","status":"awaiting_quote","priority":"normal","customer_name":"Avery","customer_phone":"0400000000","customer_email":"a@example.test","created_at":"2026-11-11T00:00:00Z","internal_notes":${notes?.let { com.google.gson.Gson().toJson(it) } ?: "null"}}"""
    @Before fun setup() {
        TokenStore.init(context); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath
                val body = request.body.readUtf8()
                if(request.method in listOf("POST", "PATCH")) writes.add(path to body)
                val response = when {
                    path == "/v1/repair-jobs" && request.method == "GET" -> {
                        val offset = request.requestUrl!!.queryParameter("offset")?.toInt() ?: 0; listOffsets.add(offset)
                        if(offset == 0) (0 until 50).joinToString(",", "[", "]") { index -> job().replace("\"id\":\"job-1\"", "\"id\":\"collected-$index\"").replace("\"status\":\"awaiting_quote\"", "\"status\":\"collected\"") } else "[${job()}]"
                    }
                    path == "/v1/job-templates" -> """[{"id":"battery","label":"Battery replacement","module":"watch","title":"Battery replacement","pre_quote_cents":4500}]"""
                    path == "/v1/watch-catalogue/repairs-config" -> """{"combos":[],"currency":"AUD"}"""
                    path == "/v1/watches/watch-1" || path == "/v1/watches" && request.method == "POST" -> """{"id":"watch-1","tenant_id":"tenant","customer_id":"customer-1","brand":"Seiko"}"""
                    path == "/v1/repair-jobs/job-1" -> {
                        if(request.method == "PATCH") notes = JsonParser.parseString(body).asJsonObject["internal_notes"].let { if(it.isJsonNull) null else it.asString }
                        job()
                    }
                    path == "/v1/repair-jobs" && request.method == "POST" -> job()
                    path == "/v1/quotes" && request.method == "POST" -> """{"id":"q1","repair_job_id":"job-1","status":"draft","subtotal_cents":1000,"tax_cents":100,"total_cents":1100,"currency":"AUD","created_at":"2026-11-11T00:00:00Z"}"""
                    path == "/v1/invoices" -> """{"items":[],"total":0}"""
                    path == "/v1/attachments" && request.method == "POST" -> {
                        photoLabels.add(request.requestUrl!!.queryParameter("label").orEmpty())
                        """{"id":"photo","tenant_id":"tenant","storage_key":"photo.jpg","file_name":"photo.jpg","content_type":"image/jpeg","file_size_bytes":100,"created_at":"2026-11-11T00:00:00Z"}"""
                    }
                    else -> "[]"
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(response)
            }
        }; server.start()
        TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("watch-parity", "tech"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun detail() = JobDetailViewModel("job-1", server.url("/").toString()).also { wait.waitUntil(10_000) { !it.state.value.loading } }

    @Test fun editableShopNotesReplaceAndClearWithoutAppendingActivity() {
        val model = detail(); var saved = false
        model.saveInternalNotes("Revised notes", "Original private notes") { saved = true }
        wait.waitUntil(10_000) { !model.state.value.noteBusy }
        Assert.assertTrue(saved); Assert.assertEquals("Revised notes", model.state.value.job?.internalNotes)
        Assert.assertEquals(listOf("/v1/repair-jobs/job-1"), writes.map { it.first })
        model.saveInternalNotes("", "Revised notes") {}
        wait.waitUntil(10_000) { !model.state.value.noteBusy }
        Assert.assertNull(notes)
        Assert.assertTrue(JsonParser.parseString(writes.last().second).asJsonObject["internal_notes"].isJsonNull)
    }
    @Test fun aConcurrentShopNoteChangePreventsAnOverwrite() {
        val model = detail(); notes = "Updated by another staff member"
        model.saveInternalNotes("My draft", "Original private notes") { Assert.fail("Conflict saved") }
        wait.waitUntil(10_000) { !model.state.value.noteBusy }
        Assert.assertTrue(model.state.value.error.orEmpty().contains("changed")); Assert.assertTrue(writes.isEmpty())
        Assert.assertEquals("Updated by another staff member", model.state.value.job?.internalNotes)
    }
    @Test fun typedWatchQuoteLinesReachTheActualCreateRequest() {
        val model = JobQuotesViewModel("job-1"); wait.waitUntil(10_000) { !model.state.value.loading }
        model.createLines(listOf(MobileQuoteLine("Movement", 1.0, 10000, itemType = "part"), MobileQuoteLine("Discount", 1.0, 1000, itemType = "discount")), true, true)
        wait.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertNull(model.state.value.error)
        val lines = JsonParser.parseString(writes.single { it.first == "/v1/quotes" }.second).asJsonObject.getAsJsonArray("line_items")
        Assert.assertEquals(listOf("part", "discount"), lines.map { it.asJsonObject["item_type"].asString })
    }
    @Test fun quotePickerCanReachAnOpenJobBeyondTheFirstFiftyClosedJobs() {
        val model = QuoteJobPickerViewModel(); wait.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertTrue(quotableJobs(model.state.value.jobs, "").isEmpty()); Assert.assertTrue(model.state.value.canLoadMore)
        model.loadMore(); wait.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals(listOf("job-1"), quotableJobs(model.state.value.jobs, "").map { it.id })
        Assert.assertEquals(listOf(0, 50), listOffsets.toList()); Assert.assertFalse(model.state.value.canLoadMore)
    }
    @Test fun templateChecklistAndSeparateFrontBackPhotosSurviveTheIntakeSave() {
        val model = WatchIntakeViewModel(SavedStateHandle()); wait.waitUntil(10_000) { model.state.value.templates.isNotEmpty() }
        model.applyTemplate("battery"); Assert.assertEquals("45.00", model.field("preQuote"))
        model.setField("customerId", "customer-1"); model.setField("watch.0.condition", "Crown loose"); model.toggleCondition(0, "scratches")
        val directory = File(context.filesDir, "intake-photos").apply { mkdirs() }
        for(side in listOf("front", "back")) {
            val file = File(directory, "watch-parity-$side.jpg")
            file.outputStream().use { Bitmap.createBitmap(16, 16, Bitmap.Config.ARGB_8888).compress(Bitmap.CompressFormat.JPEG, 90, it) }
            model.setPhoto(0, side, FileProvider.getUriForFile(context, "${context.packageName}.intake", file).toString())
        }
        model.submit(context); wait.waitUntil(15_000) { !model.state.value.busy }
        Assert.assertNull(model.state.value.error); Assert.assertTrue(model.state.value.complete)
        val watch = JsonParser.parseString(writes.single { it.first == "/v1/watches" }.second).asJsonObject
        Assert.assertEquals("Crown loose\nCondition: scratches", watch["condition_notes"].asString)
        Assert.assertEquals(listOf("watch_front", "watch_back"), photoLabels.toList())
    }
    @Test fun longIntakeNotesPaginateAndUnbrokenWordsFitThePrintedColumn() {
        val copy = IntakeTicketCopy("Repair", "Workshop", listOf("Condition" to "x".repeat(4000)), "Scan")
        val pages = paginateIntakeCopy(copy)
        Assert.assertTrue(pages.size > 1)
        val paint = Paint().apply { textSize = 13f }
        Assert.assertTrue(wrapText("x".repeat(4000), paint, 385f).all { paint.measureText(it) <= 385f })
        for(page in pages) {
            val height = page.rows.sumOf { maxOf(1, wrapText(it.second, paint, 385f).size) * 17 + 10 }
            Assert.assertTrue(height <= 450)
            drawIntakeCopy(Canvas(Bitmap.createBitmap(595, 842, Bitmap.Config.ARGB_8888)), page, QrCode.encode("https://mainspring.test/jobs/1"))
        }
    }
}
