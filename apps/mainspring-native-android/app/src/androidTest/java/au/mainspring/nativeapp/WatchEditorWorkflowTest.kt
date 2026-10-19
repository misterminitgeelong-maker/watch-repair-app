package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.WatchEditorScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class WatchEditorWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var serial: String? = "QA-001"
    private var customer = "customer-1"
    private var creates = 0
    private var patches = 0
    private var createBody = ""
    private var patch = ""
    private var unknown = false
    private val offsets = ConcurrentLinkedQueue<Int>()
    private fun watch(id: String = "watch-1") = """{"id":"$id","customer_id":"$customer","brand":"Test brand","model":"Test model","serial_number":${serial?.let { "\"$it\"" } ?: "null"},"movement_type":"quartz","condition_notes":"Existing marks"}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val body = when(request.path.orEmpty().substringBefore('?')) {
                    "/v1/watches" -> if(request.method == "POST") {
                        creates++; createBody = request.body.readUtf8()
                        if(unknown) return MockResponse().setResponseCode(503).setBody("Unknown creation")
                        watch()
                    } else {
                        Assert.assertEquals("customer-1", request.requestUrl!!.queryParameter("customer_id"))
                        val offset = request.requestUrl!!.queryParameter("offset")!!.toInt(); offsets.add(offset)
                        val end = if(offset == 0) 200 else 201
                        (offset until end).joinToString(",", "[", "]") { watch("watch-$it") }
                    }
                    "/v1/watches/watch-1" -> {
                        if(request.method == "PATCH") {
                            patches++; patch = request.body.readUtf8()
                            val json = JsonParser.parseString(patch).asJsonObject
                            if(json.has("serial_number")) serial = json["serial_number"].takeUnless { it.isJsonNull }?.asString
                        }
                        watch()
                    }
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("watch-editor", "clerk"); TokenStore.setSessionRole("clerk")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun editing() = WatchEditorViewModel("customer-1", "watch-1").also { compose.waitUntil(10_000) { !it.state.value.loading } }
    @Test fun standaloneWatchCreationUsesCustomerAndRetainsAcknowledgedId() {
        val model = WatchEditorViewModel("customer-1", "")
        compose.setContent { MainspringTheme { WatchEditorScreen("customer-1", "", {}, {}, model) } }
        compose.onNodeWithText("Brand").performTextInput("Test brand")
        compose.onNodeWithText("Save new watch").performScrollTo().performClick()
        compose.waitUntil(10_000) { !model.state.value.busy && model.state.value.saved }
        Assert.assertEquals("customer-1", JsonParser.parseString(createBody).asJsonObject["customer_id"].asString)
        val restored = WatchEditorViewModel("customer-1", ""); restored.save()
        Assert.assertEquals("watch-1", restored.state.value.createdId); Assert.assertEquals(1, creates)
        restored.another(); Assert.assertNull(restored.state.value.createdId)
    }
    @Test fun watchEditUsesChangedOnlyPatchAndExplicitNullForClearingSerial() {
        val model = editing(); model.set("serial_number", ""); model.save()
        compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertTrue(model.state.value.saved)
        val json = JsonParser.parseString(patch).asJsonObject
        Assert.assertEquals(setOf("serial_number"), json.keySet()); Assert.assertTrue(json["serial_number"].isJsonNull)
        model.save(); compose.waitUntil(10_000) { !model.state.value.busy }; Assert.assertEquals(1, patches)
    }
    @Test fun unknownCreationReviewsAllCustomerWatchesBeforeExistingRecordRecovery() {
        unknown = true
        val model = WatchEditorViewModel("customer-1", ""); model.set("brand", "Test brand"); model.save()
        compose.waitUntil(10_000) { !model.state.value.busy }; Assert.assertTrue(model.state.value.uncertain)
        val restored = WatchEditorViewModel("customer-1", ""); restored.save(); Assert.assertEquals(1, creates)
        restored.review(); compose.waitUntil(10_000) { !restored.state.value.loading }
        Assert.assertEquals(listOf(0, 200), offsets.toList()); Assert.assertEquals(201, restored.state.value.matches.size)
        restored.useExisting("watch-200"); Assert.assertEquals("watch-200", restored.state.value.createdId); Assert.assertFalse(restored.state.value.uncertain)
    }
    @Test fun peerEditAndChangedOwnershipBlockWatchPatch() {
        val model = editing(); model.set("model", "Draft model"); serial = "OTHER-SERIAL"
        model.save(); compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertEquals(0, patches); Assert.assertTrue(model.state.value.conflict)
        model.load(discard = true); compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals("OTHER-SERIAL", model.state.value.fields["serial_number"])
        customer = "customer-2"; model.set("model", "Updated model"); model.save(); compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertEquals(0, patches); Assert.assertTrue(model.state.value.conflict)
    }
}
