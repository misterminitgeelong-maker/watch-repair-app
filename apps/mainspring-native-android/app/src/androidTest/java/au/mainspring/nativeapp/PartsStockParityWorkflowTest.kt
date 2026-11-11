package au.mainspring.nativeapp

import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.*
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Exercises the native stock, transfer and purchase UI against the current shop endpoint shapes. */
class PartsStockParityWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val writes = ConcurrentLinkedQueue<Pair<String, String>>()
    @Volatile private var used = false
    @Volatile private var received = false
    @Volatile private var stockQuantity = 3
    private val transfer get() = """{"id":"incoming","status":"${if(received) "received" else "in_transit"}","from_location_id":"other","to_location_id":"mine","lines":[{"part_id":"sole","sku":"SOLE-41","name":"Sole size 41","quantity":2,"received_quantity":${if(received) 2 else 0}}]}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        writes.clear(); used = false; received = false; stockQuantity = 3
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath
                val json = MockResponse().setHeader("Content-Type", "application/json")
                val postBody = if(request.method == "POST") request.body.readUtf8().also { writes += path to it } else ""
                return when {
                    path == "/v1/stock/locations" -> json.setBody("""[{"id":"mine","name":"Geelong","kind":"shop","mine":true,"active":true},{"id":"other","name":"Workshop","kind":"workshop","mine":false,"active":true}]""")
                    path == "/v1/stock/models" -> json.setBody("""[{"id":"arizona","name":"Arizona","active":true}]""")
                    path == "/v1/stock/levels" -> json.setBody("""[{"location_id":"mine","location_name":"Geelong","part_id":"sole","sku":"SOLE-41","name":"Sole size 41","quantity":$stockQuantity,"reorder_level":5,"low":${stockQuantity <= 5}}]""")
                    path == "/v1/stock/transfers" && request.method == "GET" -> json.setBody("[$transfer]")
                    path == "/v1/stock/transfers" -> json.setBody("""{"id":"outgoing","status":"in_transit","from_location_id":"mine","to_location_id":"other","lines":[]}""")
                    path == "/v1/stock/transfers/incoming/receive" -> { if(!received) stockQuantity += 2; received = true; json.setBody(transfer) }
                    path == "/v1/stock/adjust" -> {
                        val fields = JsonParser.parseString(postBody).asJsonObject
                        val quantity = fields["quantity"].asInt
                        stockQuantity = if(fields["kind"].asString == "set_count") quantity else stockQuantity + quantity
                        json.setBody("""{"quantity":$stockQuantity}""")
                    }
                    path == "/v1/stock/jobs/job/suggested-parts" -> json.setBody("""[{"part_id":"sole","sku":"SOLE-41","name":"Sole size 41","quantity":1,"in_stock":3}]""")
                    path == "/v1/stock/jobs/job/parts" && request.method == "POST" -> { used = true; json.setBody("""{"id":"use","part_id":"sole","sku":"SOLE-41","name":"Sole size 41","quantity":1,"location_id":"mine","stock_left":2}""") }
                    path == "/v1/stock/jobs/job/parts" -> json.setBody(if(used) """[{"id":"use","part_id":"sole","sku":"SOLE-41","name":"Sole size 41","quantity":1,"location_id":"mine"}]""" else "[]")
                    path == "/v1/stock/purchases/search" -> json.setBody("""[{"id":"receipt","purchase_ref":"R17","purchase_date":"2026-10-01","store":"Geelong","customer_name":"Avery","model_name":"Arizona","size":"41"}]""")
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("parts", "clerk"); TokenStore.setSessionRole("clerk")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun awaitTag(tag: String) = compose.waitUntil(10_000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() }
    private fun stockField(tag: String): SemanticsNodeInteraction {
        compose.onNodeWithTag("parts-stock").performScrollToNode(hasTestTag(tag))
        compose.waitUntil(10_000) { runCatching { compose.onNodeWithTag(tag).assertIsEnabled(); true }.getOrDefault(false) }
        return compose.onNodeWithTag(tag)
    }
    @Test fun staffCanReceiveStockAndRecordAnExactCount() {
        compose.setContent { MainspringTheme { PartsStockScreen({}) } }
        awaitTag("receive-transfer-incoming")
        saveNativeQaImage(compose.onRoot(), "parity-20261111-parts-stock.png")
        compose.onNodeWithTag("receive-transfer-incoming").performScrollTo().performClick()
        compose.onNodeWithText("Confirm").performClick()
        compose.waitUntil(10_000) { writes.any { it.first.endsWith("/receive") } }
        stockField("stock-sku").performTextInput("SOLE-41")
        compose.onNodeWithTag("stock-quantity").performScrollTo().performTextReplacement("4")
        compose.onNodeWithText("Set count to").performScrollTo().performClick()
        compose.onNodeWithTag("stock-save").performScrollTo().performClick()
        compose.onNodeWithText("Confirm").performClick()
        compose.waitUntil(10_000) { writes.any { it.first == "/v1/stock/adjust" } }
        val body = JsonParser.parseString(writes.first { it.first.endsWith("/adjust") }.second).asJsonObject
        Assert.assertEquals("mine", body["location_id"].asString); Assert.assertEquals("SOLE-41", body["sku"].asString)
        Assert.assertEquals(4, body["quantity"].asInt); Assert.assertEquals("set_count", body["kind"].asString)
        stockField("stock-sku") // Wait for the refresh following the acknowledged stock write.
        compose.onNodeWithTag("parts-stock").performScrollToNode(hasText("4 in stock · Low (reorder 5)"))
        compose.onNodeWithText("4 in stock · Low (reorder 5)").assertExists()
    }
    @Test fun transferSendsItsLocationsAndWholeQuantities() {
        compose.setContent { MainspringTheme { PartsStockScreen({}) } }
        awaitTag("receive-transfer-incoming")
        stockField("transfer-sku").performTextInput("SOLE-41")
        compose.onNodeWithTag("transfer-quantity").performScrollTo().performTextReplacement("2")
        compose.onNodeWithText("Add line").performScrollTo().performClick()
        compose.onNodeWithText("Workshop", useUnmergedTree = true).performScrollTo().performClick()
        compose.onNodeWithTag("transfer-send").performScrollTo().performClick()
        compose.onNodeWithText("Confirm").performClick()
        compose.waitUntil(10_000) { writes.any { it.first == "/v1/stock/transfers" } }
        val body = JsonParser.parseString(writes.first { it.first == "/v1/stock/transfers" }.second).asJsonObject
        Assert.assertEquals("mine", body["from_location_id"].asString); Assert.assertEquals("other", body["to_location_id"].asString)
        Assert.assertEquals(2, body.getAsJsonArray("lines")[0].asJsonObject["quantity"].asInt)
    }
    @Test fun jobPartIsConsumedOnceAndThenShownAsUsed() {
        compose.setContent { MainspringTheme { ShoeJobPartsCard("job", "Arizona/41") } }
        awaitTag("use-part-sole")
        compose.onNodeWithTag("use-part-sole").performClick(); compose.onNodeWithText("Use part").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Used: 1 × Sole size 41").fetchSemanticsNodes().isNotEmpty() }
        Assert.assertEquals(1, writes.count { it.first == "/v1/stock/jobs/job/parts" })
        val body = JsonParser.parseString(writes.first { it.first == "/v1/stock/jobs/job/parts" }.second).asJsonObject
        Assert.assertEquals("sole", body["part_id"].asString); Assert.assertEquals("mine", body["location_id"].asString)
        compose.onAllNodesWithTag("use-part-sole").assertCountEquals(0)
    }
    @Test fun purchaseLookupPopulatesTheEditableShoeFields() {
        var saved: ShoePurchaseDetails? = null
        compose.setContent { MainspringTheme { EditShoeDetailsDialog(ShoeRead("shoe"), false, {}, { _, _, _, _, purchase -> saved = purchase }) } }
        awaitTag("shoe-purchase-search")
        compose.onNodeWithTag("shoe-purchase-search").performScrollTo().performTextInput("R17")
        compose.onNodeWithText("Search purchases").performScrollTo().performClick()
        awaitTag("shoe-purchase-receipt")
        compose.onNodeWithTag("shoe-purchase-receipt").performScrollTo().performClick()
        compose.onNodeWithText("Save").performClick()
        Assert.assertEquals(ShoePurchaseDetails("Arizona", "41", "01/10/2026", "Geelong", "R17"), saved)
    }
}
