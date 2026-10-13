package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.StocktakeScreen
import au.mainspring.nativeapp.ui.screens.StockScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class StockWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var counted: Double? = null
    private var notes: String? = null
    private var status = "in_progress"
    private var loseResponse = false
    private var writes = 0
    private var creates = 0
    private var completes = 0
    private var creationBody = ""
    private var loseCreate = false
    private var loseCompletion = false
    private var created = false
    private var systemQuantity = 10.0
    private val offsets = ConcurrentLinkedQueue<Int>()
    private fun line() = """{"id":"line-1","stock_item_id":"item-1","item_code":"BAT-01","group_code":"BAT","expected_qty":10,"system_stock_qty":$systemQuantity,"counted_qty":$counted,"notes":${notes?.let { "\"$it\"" } ?: "null"},"full_description":"Watch battery"}"""
    private fun session() = """{"id":"session-1","name":"October count","status":"$status","created_at":"2026-10-08T00:00:00Z","progress":{"total_items":1,"counted_items":${if(counted == null) 0 else 1}},"lines":[${line()}]}"""
    private fun report() = """{"session":${session()},"matched_item_count":0,"missing_item_count":1,"over_count_item_count":0,"total_variance_qty":-2,"total_variance_value_cents":-200}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = when(path) {
                    "/v1/stocktakes" -> if(request.method == "POST") {
                        creates++; creationBody = request.body.readUtf8(); created = true
                        if(loseCreate) return MockResponse().setResponseCode(503).setBody("Unknown creation")
                        session().replace("session-1", "session-2").replace("October count", "Battery count")
                    } else "[${session()}${if(created) "," + session().replace("session-1", "session-2").replace("October count", "Battery count") else ""}]"
                    "/v1/stocktakes/session-1" -> session()
                    "/v1/stocktakes/session-1/report" -> report()
                    "/v1/stocktakes/session-1/complete" -> {
                        completes++; status = "completed"
                        if(loseCompletion) return MockResponse().setResponseCode(503).setBody("Unknown completion")
                        report()
                    }
                    "/v1/stocktakes/session-1/lines/line-1" -> {
                        Assert.assertEquals("PATCH", request.method); writes++
                        val payload = JsonParser.parseString(request.body.readUtf8()).asJsonObject
                        counted = payload["counted_qty"].asDouble; notes = payload["notes"].asString
                        if(loseResponse) return MockResponse().setResponseCode(503).setBody("Unknown result")
                        line()
                    }
                    "/v1/stock/items" -> {
                        val offset = request.requestUrl!!.queryParameter("offset")!!.toInt(); offsets.add(offset)
                        val search = request.requestUrl!!.queryParameter("search")
                        val suffix = if(search == null) offset.toString() else search
                        """{"items":[{"id":"item-$suffix","item_code":"BAT-$suffix","group_code":"BAT","system_stock_qty":10,"pack_qty":1,"cost_price_cents":100,"retail_price_cents":200}],"total":2,"limit":1,"offset":$offset}"""
                    }
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("stock", "clerk"); TokenStore.setSessionRole("clerk")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun model() = StocktakeViewModel("session-1").also { compose.waitUntil(10_000) { !it.state.value.loading } }
    @Test fun inventoryPagingAndFilteredSearchResetOffsets() {
        val model = StockViewModel(); compose.waitUntil(10_000) { !model.state.value.loading }
        model.more(); compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals(listOf(0, 1), offsets.toList()); Assert.assertEquals(2, model.state.value.items.size)
        model.search("battery"); compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals(0, offsets.last()); Assert.assertEquals("item-battery", model.state.value.items.single().id)
    }
    @Test fun countRequiresConfirmationAndStoresFractionalQuantityWithoutAdjustingInventory() {
        val model = model()
        compose.setContent { MainspringTheme { StocktakeScreen("session-1", {}, model) } }
        compose.onNodeWithText("Count BAT-01").performScrollTo().performClick()
        compose.onNodeWithText("Counted quantity").performScrollTo().performTextReplacement("8.5")
        compose.onNodeWithText("Save count").performScrollTo().performClick()
        Assert.assertEquals(0, writes)
        compose.onNodeWithText("Confirm save").performClick()
        compose.waitUntil(10_000) { !model.state.value.busy && !model.state.value.loading && writes == 1 }
        Assert.assertEquals(8.5, counted!!, 0.0); Assert.assertEquals("", model.state.value.lineId)
        Assert.assertEquals("in_progress", model.state.value.session!!.status)
        saveNativeQaImage(compose.onRoot(), "stocktake-count.png")
    }
    @Test fun changedCountBlocksOverwriteAndCompletedStocktakeIsReadOnly() {
        val model = model(); model.select(model.state.value.session!!.lines!!.single()); model.count("8")
        counted = 9.0; model.save(); compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertEquals(0, writes); Assert.assertTrue(model.state.value.conflict)
        model.discard(); status = "completed"; model.refresh(); compose.waitUntil(10_000) { !model.state.value.loading }
        model.select(model.state.value.session!!.lines!!.single()); model.save()
        Assert.assertEquals(0, writes); Assert.assertEquals("", model.state.value.lineId)
    }
    @Test fun unknownAcknowledgedCountRecoversAcrossRecreationWithoutAnotherPatch() {
        loseResponse = true
        val model = model(); model.select(model.state.value.session!!.lines!!.single()); model.count("7.25"); model.notes("Shelf count"); model.save()
        compose.waitUntil(10_000) { !model.state.value.busy }; Assert.assertTrue(model.state.value.uncertain)
        val restored = model(); Assert.assertFalse(restored.state.value.uncertain); Assert.assertEquals("", restored.state.value.lineId)
        restored.save(); Assert.assertEquals(1, writes); Assert.assertEquals(7.25, restored.state.value.session!!.lines!!.single().counted!!, 0.0)
    }
    @Test fun invalidNegativeCountAndNonFiniteCountDoNotWrite() {
        val model = model(); model.select(model.state.value.session!!.lines!!.single())
        model.count("NaN"); model.save(); Assert.assertEquals(0, writes)
        model.count("-2"); model.save(); Assert.assertEquals(0, writes)
        model.negative(true); model.save(); compose.waitUntil(10_000) { !model.state.value.busy && !model.state.value.loading }
        Assert.assertEquals(1, writes); Assert.assertEquals(-2.0, counted!!, 0.0)
    }
    @Test fun creationConfirmsFilterScopeAndRetainsCreatedIdAcrossRecreation() {
        val model = StockViewModel(); compose.waitUntil(10_000) { !model.state.value.loading }
        model.search("battery"); model.group("BAT"); model.hideZero(true)
        compose.waitUntil(10_000) { !model.state.value.loading }
        compose.setContent { MainspringTheme { StockScreen({}, {}, model) } }
        compose.onNodeWithText("New stocktake from filters").performScrollTo().performClick()
        compose.onNodeWithText("Stocktake name").performTextReplacement("Battery count")
        Assert.assertEquals(0, creates)
        compose.onNodeWithText("Confirm creation").performClick()
        compose.waitUntil(10_000) { !model.state.value.creating && model.state.value.createdId != null }
        val body = JsonParser.parseString(creationBody).asJsonObject
        Assert.assertEquals("battery", body["search"].asString); Assert.assertEquals("BAT", body["group_code"].asString); Assert.assertTrue(body["hide_zero_stock"].asBoolean)
        val restored = StockViewModel(); restored.create(); Assert.assertEquals("session-2", restored.state.value.createdId); Assert.assertEquals(1, creates)
    }
    @Test fun unknownCreationRequiresFreshDirectoryReviewAndCanUseExistingSession() {
        loseCreate = true
        val model = StockViewModel(); compose.waitUntil(10_000) { !model.state.value.loading }
        model.name("Battery count"); model.create(); compose.waitUntil(10_000) { !model.state.value.creating }
        Assert.assertTrue(model.state.value.unknownCreate)
        val restored = StockViewModel(); compose.waitUntil(10_000) { restored.state.value.directoryReviewed && !restored.state.value.loading }
        restored.create(); Assert.assertEquals(1, creates)
        restored.useExisting("session-2"); Assert.assertFalse(restored.state.value.unknownCreate); Assert.assertEquals("session-2", restored.state.value.createdId)
    }
    @Test fun completionRequiresManagerEveryCountAndUserConfirmation() {
        val model = model(); model.complete(); Assert.assertEquals(0, completes)
        TokenStore.setSessionRole("manager"); model.complete(); Assert.assertEquals(0, completes)
        counted = 8.0; model.refresh(); compose.waitUntil(10_000) { !model.state.value.loading }
        compose.setContent { MainspringTheme { StocktakeScreen("session-1", {}, model) } }
        compose.onNodeWithText("Complete stocktake").performScrollTo().performClick()
        Assert.assertEquals(0, completes); compose.onNodeWithText("Confirm completion").performClick()
        compose.waitUntil(10_000) { !model.state.value.busy && model.state.value.report != null }
        Assert.assertEquals(1, completes); Assert.assertEquals("completed", model.state.value.session!!.status)
        model.complete(); Assert.assertEquals(1, completes)
    }
    @Test fun lostCompletionResponseRecoversCompletedStatusWithoutReplayingPost() {
        TokenStore.setSessionRole("owner"); counted = 8.0; loseCompletion = true
        val model = model(); model.complete(); compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertTrue(model.state.value.completionUnknown)
        val restored = model(); compose.waitUntil(10_000) { restored.state.value.report != null }
        Assert.assertFalse(restored.state.value.completionUnknown); Assert.assertEquals("completed", restored.state.value.session!!.status)
        restored.complete(); Assert.assertEquals(1, completes)
    }
    @Test fun changedCountsBlockCompletionUntilLatestStocktakeIsReviewed() {
        TokenStore.setSessionRole("owner"); counted = 8.0
        val model = model(); counted = 6.0; model.complete(); compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertEquals(0, completes); Assert.assertEquals(6.0, model.state.value.session!!.lines!!.single().counted!!, 0.0)
        Assert.assertTrue(model.state.value.error!!.contains("changed"))
    }
    @Test fun changedSystemInventoryAlsoBlocksCompletionUntilReviewed() {
        TokenStore.setSessionRole("owner"); counted = 8.0
        val model = model(); systemQuantity = 14.0
        model.complete(); compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertEquals(0, completes)
        Assert.assertEquals(14.0, model.state.value.session!!.lines!!.single().systemQuantity!!, 0.0)
        Assert.assertTrue(model.state.value.error!!.contains("changed"))
    }
}
