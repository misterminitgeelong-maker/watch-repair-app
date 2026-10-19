package au.mainspring.nativeapp

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.QuoteSignatureScreen
import okhttp3.mockwebserver.*
import okio.Buffer
import org.junit.*
import java.util.concurrent.TimeUnit

class QuoteSignatureWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private var hasSignature = true
    private var invalidImage = false
    private var hugeImage = false
    private var redirect: String? = null
    private var downloads = 0
    private var refreshes = 0
    private lateinit var png: ByteArray
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        val bitmap = Bitmap.createBitmap(1000, 300, Bitmap.Config.ARGB_8888)
        Canvas(bitmap).drawText("Avery QA", 40f, 200f, Paint().apply { color = Color.BLACK; textSize = 90f; isAntiAlias = true })
        png = java.io.ByteArrayOutputStream().also { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray(); bitmap.recycle()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when(request.path) {
                "/v1/auto-key-jobs/job-1/quotes" -> MockResponse().setHeader("Content-Type", "application/json").setBody("""[{"id":"quote-1","status":"approved","subtotal_cents":1000,"tax_cents":100,"total_cents":1100,"currency":"AUD","signer_name":"Avery QA","signed_at":"2026-10-08T00:00:00Z","has_signature":$hasSignature}]""")
                "/v1/auto-key-jobs/quotes/quote-1/signature" -> {
                    downloads++
                    if(redirect != null) MockResponse().setResponseCode(302).setHeader("Location", redirect!!)
                    else MockResponse().setHeader("Content-Type", "image/png").setBody(Buffer().write(if(hugeImage) ByteArray(2_000_001) else if(invalidImage) "invalid image".toByteArray() else png))
                }
                "/v1/auth/refresh" -> { refreshes++; MockResponse().setHeader("Content-Type", "application/json").setBody("""{"access_token":"unexpected-test-token","refresh_token":"unexpected-refresh"}""") }
                else -> MockResponse().setResponseCode(404)
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.saveTokens("synthetic-test-token", "synthetic-test-refresh"); TokenStore.setDraftScope("signature", "tech"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun model(quoteId: String = "quote-1") = QuoteSignatureViewModel("job-1", quoteId).also { compose.waitUntil(10_000) { !it.state.value.loading } }
    @Test fun authenticatedSignatureDisplaysSignerDateAndImage() {
        val model = model(); Assert.assertNotNull(model.state.value.bitmap); Assert.assertNull(model.state.value.error); Assert.assertEquals(1, downloads)
        compose.setContent { MainspringTheme { QuoteSignatureScreen("job-1", "quote-1", {}, model) } }
        compose.onNodeWithText("Signed by Avery QA").assertExists()
        compose.onNodeWithContentDescription("Customer's recorded quote signature").assertIsDisplayed()
        saveNativeQaImage(compose.onRoot(), "quote-signature.png")
    }
    @Test fun missingSignatureOrQuoteDoesNotRequestImage() {
        hasSignature = false
        Assert.assertTrue(model().state.value.error!!.contains("No customer signature")); Assert.assertEquals(0, downloads)
        Assert.assertTrue(model("other-quote").state.value.error!!.contains("selected job")); Assert.assertEquals(0, downloads)
    }
    @Test fun malformedAndOversizedImagesAreRejected() {
        invalidImage = true; Assert.assertNull(model().state.value.bitmap)
        invalidImage = false; hugeImage = true
        val model = model(); Assert.assertNull(model.state.value.bitmap); Assert.assertTrue(model.state.value.error!!.contains("file size"))
    }
    @Test fun signedStorage401DoesNotReceiveBearerRetryOrExpireShopSession() {
        val storage = MockWebServer(); storage.enqueue(MockResponse().setResponseCode(401)); storage.start()
        try {
            redirect = storage.url("/signature.png").toString()
            val model = model(); Assert.assertNull(model.state.value.bitmap)
            val received = storage.takeRequest(2, TimeUnit.SECONDS)!!
            Assert.assertNull(received.getHeader("Authorization")); Assert.assertEquals(1, storage.requestCount)
            Assert.assertEquals(0, refreshes); Assert.assertEquals("synthetic-test-token", TokenStore.getAccessToken())
            Assert.assertTrue(model.state.value.error!!.contains("download link"))
        } finally { storage.shutdown() }
    }
    @Test fun clerkCannotDownloadStaffSignature() {
        TokenStore.setSessionRole("clerk")
        val model = model(); Assert.assertEquals(0, server.requestCount); Assert.assertTrue(model.state.value.error!!.contains("technician or manager"))
    }
}
